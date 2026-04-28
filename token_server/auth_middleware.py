import os
from functools import wraps
from flask import request, g, abort
import firebase_admin
from firebase_admin import credentials, auth

def init_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred_path:
            local_key = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "serviceAccountKey.json")
            if os.path.exists(local_key):
                cred_path = local_key
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        init_firebase()
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            abort(401)
        token = header.split(" ", 1)[1].strip()
        try:
            decoded = auth.verify_id_token(token)
            g.user_id = decoded.get("uid")
        except Exception:
            abort(401)
        return f(*args, **kwargs)
    return wrapper
