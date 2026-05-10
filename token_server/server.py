"""
server.py – Token Server for SignSpeak (Agora RTC token generation).

POST /token   Generate an Agora RTC token
GET  /health  Liveness probe
"""

import logging
import os
import sys
import time
import requests

from flask import Flask, abort, jsonify, request, g
from flask_cors import CORS
from firebase_admin import auth, firestore
from auth_middleware import require_auth
from firestore_client import FirestoreClient

try:
    from firebase_admin import messaging
    HAS_FCM = True
except ImportError:
    HAS_FCM = False
    messaging = None

# ── Logging ─────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask app ───────────────────────────────────────
app = Flask(__name__)
CORS(app)

firestore_client = FirestoreClient()

DEFAULT_TTL = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))


# ── Agora Token Builder ─────────────────────────────
# Implements Agora AccessToken2 (RTC) generation from scratch
# Compatible with Agora SDK 4.x
import base64
import hashlib
import hmac
import struct
import zlib


ROLE_PUBLISHER   = 1
ROLE_SUBSCRIBER  = 2

# Privilege codes for AccessToken2
PRIVILEGE_JOIN_CHANNEL         = 1
PRIVILEGE_PUBLISH_AUDIO_STREAM = 2
PRIVILEGE_PUBLISH_VIDEO_STREAM = 3
PRIVILEGE_PUBLISH_DATA_STREAM  = 4


def _pack_uint16(x: int) -> bytes:
    return struct.pack("<H", x)

def _pack_uint32(x: int) -> bytes:
    return struct.pack("<I", x)

def _pack_int32(x: int) -> bytes:
    return struct.pack("<i", x)

def _pack_string(s: str) -> bytes:
    encoded = s.encode("utf-8")
    return _pack_uint16(len(encoded)) + encoded

def _pack_map_uint32(m: dict) -> bytes:
    result = _pack_uint16(len(m))
    for k, v in sorted(m.items()):
        result += _pack_uint16(k) + _pack_uint32(v)
    return result


def build_token_with_uid(
    app_id: str,
    app_certificate: str,
    channel_name: str,
    uid: int,
    role: int,
    token_expire: int,
    privilege_expire: int,
) -> str:
    """
    Build a proper Agora AccessToken2 for RTC.
    This is compatible with agora_rtc_engine 6.x / Agora SDK 4.x.
    """
    now_ts = int(time.time())
    expire_ts = now_ts + token_expire
    priv_expire_ts = now_ts + privilege_expire

    # Privileges map
    privileges = {
        PRIVILEGE_JOIN_CHANNEL: priv_expire_ts,
    }
    if role == ROLE_PUBLISHER:
        privileges[PRIVILEGE_PUBLISH_AUDIO_STREAM] = priv_expire_ts
        privileges[PRIVILEGE_PUBLISH_VIDEO_STREAM] = priv_expire_ts
        privileges[PRIVILEGE_PUBLISH_DATA_STREAM]  = priv_expire_ts

    # Build message (the content that gets signed)
    uid_str = "" if uid == 0 else str(uid)
    msg = (
        _pack_uint32(now_ts)
        + _pack_uint32(expire_ts)
        + _pack_string(channel_name)
        + _pack_string(uid_str)
        + _pack_map_uint32(privileges)
    )

    # Sign: HMAC-SHA256(app_certificate, app_id + channel_name + uid_str + msg)
    sign_msg = app_id.encode("utf-8") + channel_name.encode("utf-8") + uid_str.encode("utf-8") + msg
    signature = hmac.new(
        app_certificate.encode("utf-8"),
        sign_msg,
        hashlib.sha256,
    ).digest()

    # Compress the message body
    compressed = zlib.compress(signature + msg)

    # Encode: version (007) + app_id + base64(compressed)
    token_bytes = b"007" + app_id.encode("utf-8") + base64.b64encode(compressed)
    return token_bytes.decode("ascii")


def _generate_agora_token(channel_id: str, uid_str: str, role_str: str, ttl: int):
    """Internal helper to generate an Agora token and update Firestore."""
    # 1. Update Firestore state
    try:
        count = firestore_client.add_participant(channel_id, uid_str)
        logger.info("Participant %s joined channel %s (total: %d)", uid_str, channel_id, count)
    except Exception as exc:
        logger.warning("Failed to update Firestore participants: %s", exc)

    app_id = os.environ.get("AGORA_APP_ID", "")
    app_cert = os.environ.get("AGORA_APP_CERTIFICATE", "")

    if not app_id or not app_cert:
        logger.warning("AGORA credentials missing – returning empty token")
        return {
            "token": "",
            "role": role_str,
            "expiresIn": ttl,
            "expiresAt": int(time.time()) + ttl,
            "channelId": channel_id,
            "uid": uid_str,
        }

    # 2. UID conversion
    if uid_str.isdigit():
        uid_int = int(uid_str)
    else:
        hasher = hashlib.md5(uid_str.encode("utf-8"))
        uid_int = int(hasher.hexdigest()[:8], 16) & 0x7FFFFFFF

    role = ROLE_PUBLISHER if role_str == "publisher" else ROLE_SUBSCRIBER

    # 3. Build token
    try:
        agora_token = build_token_with_uid(
            app_id=app_id,
            app_certificate=app_cert,
            channel_name=channel_id,
            uid=uid_int,
            role=role,
            token_expire=ttl,
            privilege_expire=ttl,
        )
    except Exception as exc:
        logger.error("Token build failed: %s", exc)
        raise exc

    expire_ts = int(time.time()) + ttl

    # 4. Audit
    try:
        firestore_client.record_token_issued(channel_id, uid_str, expire_ts)
    except Exception as exc:
        logger.warning("Failed to record token audit: %s", exc)

    return {
        "token": agora_token,
        "appId": app_id,
        "role": role_str,
        "expiresIn": ttl,
        "expiresAt": expire_ts,
        "channelId": channel_id,
        "uid": uid_str,
    }


# ── Routes ──────────────────────────────────────────
@app.route("/token", methods=["POST"])
@require_auth
def token():
    data = request.get_json(silent=True) or {}

    channel_id = str(data.get("channelId", "")).strip()
    uid_str    = str(data.get("uid", g.user_id)).strip()
    role_str   = str(data.get("role", "publisher")).strip()
    ttl        = int(data.get("ttlSeconds", DEFAULT_TTL))

    if not channel_id:
        abort(400, "'channelId' is required.")
    if ttl <= 0 or ttl > 86400:
        abort(400, "ttlSeconds must be between 1 and 86400.")

    try:
        response_data = _generate_agora_token(channel_id, uid_str, role_str, ttl)
        return jsonify(response_data)
    except Exception as exc:
        abort(500, f"Token generation failed: {exc}")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/ready", methods=["GET"])
def ready():
    return jsonify({"ready": True})


# ── Call Invitation Endpoints ─────────────────────────────────────────────

@app.route("/call/invite", methods=["POST"])
@require_auth
def call_invite():
    """
    Send a call invitation to a callee.
    Body: { "calleeUid": "...", "channelId": "...", "callerName": "..." }
    """
    data = request.get_json(silent=True) or {}
    callee_uid = str(data.get("calleeUid", "")).strip()
    channel_id = str(data.get("channelId", "")).strip()
    caller_name = str(data.get("callerName", "Someone")).strip()
    caller_uid = g.user_id

    if not callee_uid:
        abort(400, "'calleeUid' is required.")
    if not channel_id:
        abort(400, "'channelId' is required.")

    invite_id = firestore_client.create_call_invitation(
        channel_id=channel_id,
        caller_uid=caller_uid,
        callee_uid=callee_uid,
        caller_name=caller_name,
    )

    fcm_token = firestore_client.get_user_fcm_token(callee_uid)
    if fcm_token and HAS_FCM:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="Incoming Call",
                    body=f"{caller_name} is calling you on SignSpeak",
                ),
                data={
                    "type": "call_invitation",
                    "inviteId": invite_id,
                    "channelId": channel_id,
                    "callerUid": caller_uid,
                    "callerName": caller_name,
                },
                token=fcm_token,
            )
            messaging.send(message)
            logger.info("FCM push sent to %s for invite %s", callee_uid, invite_id)
        except Exception as exc:
            logger.warning("FCM send failed: %s", exc)
    else:
        logger.info(
            "No FCM token for user %s; invitation %s created (push skipped)",
            callee_uid,
            invite_id,
        )

    return jsonify({"inviteId": invite_id, "status": "sent"})


@app.route("/call/respond", methods=["POST"])
@require_auth
def call_respond():
    """
    Accept or reject a call invitation.
    Body: { "inviteId": "...", "action": "accept|reject" }
    """
    data = request.get_json(silent=True) or {}
    invite_id = str(data.get("inviteId", "")).strip()
    action = str(data.get("action", "")).strip()
    uid = g.user_id

    if not invite_id:
        abort(400, "'inviteId' is required.")
    if action not in ("accept", "reject"):
        abort(400, "'action' must be 'accept' or 'reject'.")

    invite = firestore_client.get_call_invitation(invite_id)
    if not invite:
        abort(404, "Invitation not found.")
    if invite.get("calleeUid") != uid:
        abort(403, "Not your invitation.")

    new_status = "accepted" if action == "accept" else "rejected"
    firestore_client.update_call_invitation_status(invite_id, new_status)

    response = {"inviteId": invite_id, "status": new_status}

    if action == "accept":
        channel_id = invite.get("channelId")
        if channel_id:
            # Generate token immediately so the client can join without another request
            try:
                token_data = _generate_agora_token(channel_id, uid, "publisher", DEFAULT_TTL)
                response["tokenData"] = token_data
            except Exception as exc:
                logger.error("Failed to generate token during accept: %s", exc)

    return jsonify(response)


@app.route("/call/token", methods=["POST"])
@require_auth
def call_token():
    """
    Get a token for an established call.
    Body: { "channelId": "...", "uid": "...", "role": "publisher|subscriber" }
    """
    data = request.get_json(silent=True) or {}
    channel_id = str(data.get("channelId", "")).strip()
    uid_str = str(data.get("uid", g.user_id)).strip()
    role_str = str(data.get("role", "publisher")).strip()
    ttl = int(data.get("ttlSeconds", DEFAULT_TTL))

    if not channel_id:
        abort(400, "'channelId' is required.")

    # Mark any pending/accepted invitation as 'active' when they join
    invite = firestore_client.get_latest_invitation_for_callee(g.user_id)
    if invite and invite.get("channelId") == channel_id:
        firestore_client.update_call_invitation_status(invite["id"], "active")
        logger.info("Call %s activated via /call/token", channel_id)

    try:
        response_data = _generate_agora_token(channel_id, uid_str, role_str, ttl)
        return jsonify(response_data)
    except Exception as exc:
        abort(500, f"Token generation failed: {exc}")


@app.route("/register-fcm-token", methods=["POST"])
@require_auth
def register_fcm_token():
    """
    Register the user's FCM token for push notifications.
    Body: { "fcmToken": "..." }
    """
    data = request.get_json(silent=True) or {}
    fcm_token = str(data.get("fcmToken", "")).strip()

    if not fcm_token:
        abort(400, "'fcmToken' is required.")

    firestore_client.register_fcm_token(g.user_id, fcm_token)
    return jsonify({"status": "registered"})


@app.route("/auth/signup", methods=["POST"])
def auth_signup():
    """
    Sign up a new user using Firebase Admin SDK.
    Body: { "name": "...", "email": "...", "password": "..." }
    """
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()

    if not email or not password:
        abort(400, "Email and password are required.")

    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=name
        )
        
        # In a real app, you might want to generate a custom token or 
        # return the user info. For now, we'll return the uid.
        # Note: Frontend expects { "token": "...", "user": { "id": "...", "name": "...", "email": "..." } }
        
        # For a real signup to work with the current frontend, we need an ID token.
        # Since Admin SDK can't give us an ID token for a password, we'll return a placeholder
        # and explain to the user.
        return jsonify({
            "token": "MOCK_TOKEN_PLEASE_USE_FIREBASE_CLIENT_SDK_FOR_REAL_AUTH",
            "user": {
                "id": user.uid,
                "name": user.display_name or name,
                "email": user.email
            }
        })
    except Exception as exc:
        logger.error("Signup failed: %s", exc)
        return jsonify({"message": str(exc)}), 400


@app.route("/auth/login", methods=["POST"])
def auth_login():
    """
    Log in a user. 
    Note: Firebase Admin SDK does not support password validation.
    This route normally requires the Firebase Auth REST API and a Web API Key.
    """
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()

    if not email or not password:
        abort(400, "Email and password are required.")

    # This is a MOCK implementation because Admin SDK cannot verify passwords.
    # In production, you would use:
    # https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=[API_KEY]
    
    try:
        user = auth.get_user_by_email(email)
        # We can't verify password here with Admin SDK!
        # Returning mock success for demonstration if user exists.
        return jsonify({
            "token": "MOCK_TOKEN_PLEASE_USE_FIREBASE_CLIENT_SDK_FOR_REAL_AUTH",
            "user": {
                "id": user.uid,
                "name": user.display_name or "User",
                "email": user.email
            }
        })
    except Exception as exc:
        logger.error("Login failed: %s", exc)
        return jsonify({"message": "Invalid email or password"}), 401


@app.route("/auth/profile", methods=["GET"])
@require_auth
def auth_profile():
    """Get the profile of the authenticated user."""
    try:
        user = auth.get_user(g.user_id)
        return jsonify({
            "id": user.uid,
            "name": user.display_name or "User",
            "email": user.email,
            "profilePic": user.photo_url
        })
    except Exception as exc:
        abort(500, f"Failed to fetch profile: {exc}")


@app.route("/auth/logout", methods=["POST"])
@require_auth
def auth_logout():
    """Revoke refresh tokens for the user."""
    try:
        auth.revoke_refresh_tokens(g.user_id)
        return jsonify({"status": "logged out"})
    except Exception as exc:
        abort(500, f"Logout failed: {exc}")


# ── Run Server ──────────────────────────────────────
if __name__ == "__main__":
    host  = os.environ.get("TOKEN_SERVER_HOST", "0.0.0.0")
    port  = int(os.environ.get("TOKEN_SERVER_PORT", "8080"))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug)