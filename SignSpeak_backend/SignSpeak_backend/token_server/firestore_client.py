"""
firestore_client.py – Extended Firestore client for the token server.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import firebase_admin
from firebase_admin import firestore

logger = logging.getLogger(__name__)


class FirestoreClient:
    def __init__(self) -> None:
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app()
        self.db = firestore.client()

    # ── User FCM Token Management ─────────────────────────────────────────

    def register_fcm_token(self, uid: str, fcm_token: str) -> None:
        """Store or update a user's FCM registration token."""
        ref = self.db.collection("users").document(uid)
        ref.set(
            {
                "fcmToken": fcm_token,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        logger.info("FCM token registered for user %s", uid)

    def get_user_fcm_token(self, uid: str) -> Optional[str]:
        """Retrieve a user's FCM registration token."""
        doc = self.db.collection("users").document(uid).get()
        if not doc.exists:
            return None
        return doc.to_dict().get("fcmToken")

    # ── Call Invitation Helpers ────────────────────────────────────────────

    def create_call_invitation(
        self,
        channel_id: str,
        caller_uid: str,
        callee_uid: str,
        caller_name: str = "Someone",
    ) -> str:
        """Create a call invitation document. Returns invitation ID."""
        invite_ref = self.db.collection("call_invitations").document()
        invite_ref.set(
            {
                "channelId": channel_id,
                "callerUid": caller_uid,
                "callerName": caller_name,
                "calleeUid": callee_uid,
                "status": "pending",
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
        logger.info(
            "Call invitation created: %s from %s to %s",
            invite_ref.id,
            caller_uid,
            callee_uid,
        )
        return invite_ref.id

    def get_call_invitation(self, invitation_id: str) -> Optional[Dict[str, Any]]:
        """Return a call invitation document."""
        doc = self.db.collection("call_invitations").document(invitation_id).get()
        return doc.to_dict() if doc.exists else None

    def update_call_invitation_status(
        self, invitation_id: str, status: str
    ) -> None:
        """Update call invitation status: 'accepted', 'rejected', 'ended'."""
        ref = self.db.collection("call_invitations").document(invitation_id)
        ref.update(
            {
                "status": status,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )
        logger.info("Call invitation %s status updated to %s", invitation_id, status)

    def get_latest_invitation_for_callee(
        self, callee_uid: str, statuses: List[str] = ["pending", "accepted"]
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent call invitation for a callee with specific statuses."""
        query = (
            self.db.collection("call_invitations")
            .where("calleeUid", "==", callee_uid)
            .where("status", "in", statuses)
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        results = query.get()
        for doc in results:
            return {"id": doc.id, **doc.to_dict()}
        return None

    # ── Channel helpers ────────────────────────────────────────────────────

    def get_channel_participants(self, channel_id: str) -> List[str]:
        """Return the list of participant UIDs for the given channel."""
        doc = self.db.collection("chats").document(channel_id).get()
        if not doc.exists:
            return []
        data = doc.to_dict() or {}
        participants = data.get("participants") or []
        return [str(x) for x in participants]

    def add_participant(self, channel_id: str, uid: str) -> int:
        """Add a user to a channel's participant list (idempotent). Returns new count."""
        ref = self.db.collection("chats").document(channel_id)
        
        # Use a transaction to ensure we get an accurate count and update status
        @firestore.transactional
        def _update(transaction, doc_ref):
            snapshot = doc_ref.get(transaction=transaction)
            if not snapshot.exists:
                data = {
                    "participants": [uid],
                    "status": "calling",
                    "createdAt": firestore.SERVER_TIMESTAMP,
                }
                transaction.set(doc_ref, data)
                return 1
            
            data = snapshot.to_dict()
            participants = data.get("participants", [])
            if uid not in participants:
                participants.append(uid)
                new_status = "active" if len(participants) >= 2 else "calling"
                transaction.update(doc_ref, {
                    "participants": participants,
                    "status": new_status
                })
                return len(participants)
            return len(participants)

        transaction = self.db.transaction()
        count = _update(transaction, ref)
        logger.debug("Participant %s added to %s. New count: %d", uid, channel_id, count)
        return count

    def update_channel_status(self, channel_id: str, status: str) -> None:
        """Update the status of a channel (e.g., 'calling', 'active', 'ended')."""
        ref = self.db.collection("chats").document(channel_id)
        ref.update({"status": status})
        logger.info("Channel %s status updated to %s", channel_id, status)

    def remove_participant(self, channel_id: str, uid: str) -> None:
        """Remove a user from a channel's participant list."""
        ref = self.db.collection("chats").document(channel_id)
        ref.update({"participants": firestore.ArrayRemove([uid])})
        logger.debug("Removed participant %s from channel %s", uid, channel_id)

    def get_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Return full channel document or None."""
        doc = self.db.collection("chats").document(channel_id).get()
        return doc.to_dict() if doc.exists else None

    def create_channel(self, channel_id: str, creator_uid: str) -> None:
        """Create a new channel document with the creator as first participant."""
        self.db.collection("chats").document(channel_id).set(
            {
                "participants": [creator_uid],
                "createdBy": creator_uid,
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
        logger.info("Created channel %s by %s", channel_id, creator_uid)

    # ── Audit log helpers ──────────────────────────────────────────────────

    def record_token_issued(
        self, channel_id: str, uid: str, expire_ts: int
    ) -> None:
        """Write a token-issued audit record to Firestore."""
        try:
            self.db.collection("token_audit").add(
                {
                    "channelId": channel_id,
                    "uid": uid,
                    "issuedAt": firestore.SERVER_TIMESTAMP,
                    "expiresAt": expire_ts,
                }
            )
        except Exception as exc:
            # Non-fatal; don't fail the token request due to audit failure.
            logger.warning("Failed to record token audit: %s", exc)
