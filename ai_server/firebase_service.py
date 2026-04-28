"""
firebase_service.py – Firebase Storage & Firestore helpers for the AI server.
"""
import io
import os
import logging
from typing import Optional, Dict, Any

import firebase_admin
from firebase_admin import credentials, storage, firestore

logger = logging.getLogger(__name__)


def _ensure_firebase_initialized() -> None:
    """Initialize the Firebase Admin SDK if not already done."""
    try:
        firebase_admin.get_app()
    except ValueError:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        local_key = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "serviceAccountKey.json"
        )
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        elif os.path.exists(local_key):
            cred = credentials.Certificate(local_key)
        else:
            cred = credentials.ApplicationDefault()

        project_id = os.environ.get("FIREBASE_PROJECT_ID", "signspeak-20dff")
        bucket = os.environ.get(
            "FIREBASE_STORAGE_BUCKET", f"{project_id}.appspot.com"
        )
        firebase_admin.initialize_app(cred, {"storageBucket": bucket})


class FirebaseService:
    """Thin wrapper around Firebase Storage and Firestore."""

    def __init__(self) -> None:
        _ensure_firebase_initialized()
        self._db = firestore.client()
        self._bucket = storage.bucket()

    # ── Firestore helpers ──────────────────────────────────────────────────

    def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Return a Firestore document dict, or None if not found."""
        ref = self._db.collection(collection).document(doc_id)
        snap = ref.get()
        return snap.to_dict() if snap.exists else None

    def set_document(
        self, collection: str, doc_id: str, data: Dict[str, Any], merge: bool = True
    ) -> None:
        """Create or merge a Firestore document."""
        ref = self._db.collection(collection).document(doc_id)
        ref.set(data, merge=merge)
        logger.debug("Firestore set %s/%s merge=%s", collection, doc_id, merge)

    def update_document(
        self, collection: str, doc_id: str, data: Dict[str, Any]
    ) -> None:
        """Update specific fields in a Firestore document."""
        ref = self._db.collection(collection).document(doc_id)
        ref.update(data)
        logger.debug("Firestore update %s/%s", collection, doc_id)

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a Firestore document."""
        self._db.collection(collection).document(doc_id).delete()
        logger.debug("Firestore delete %s/%s", collection, doc_id)

    # ── Storage helpers ────────────────────────────────────────────────────

    def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw bytes to Firebase Storage and return the public URL."""
        blob = self._bucket.blob(destination_path)
        blob.upload_from_file(io.BytesIO(data), content_type=content_type)
        blob.make_public()
        logger.info("Uploaded %d bytes to %s", len(data), destination_path)
        return blob.public_url

    def download_bytes(self, source_path: str) -> bytes:
        """Download a file from Firebase Storage and return its bytes."""
        blob = self._bucket.blob(source_path)
        data = blob.download_as_bytes()
        logger.info("Downloaded %d bytes from %s", len(data), source_path)
        return data

    def delete_file(self, path: str) -> None:
        """Delete a file from Firebase Storage."""
        blob = self._bucket.blob(path)
        blob.delete()
        logger.info("Deleted storage file: %s", path)

    def generate_signed_url(self, path: str, expiration_seconds: int = 3600) -> str:
        """Return a signed URL for temporary access to a Storage object."""
        import datetime

        blob = self._bucket.blob(path)
        url = blob.generate_signed_url(
            expiration=datetime.timedelta(seconds=expiration_seconds),
            method="GET",
        )
        return url
