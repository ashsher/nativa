"""
app/utils/firebase_client.py — Firebase Admin SDK initialisation.

Provides a shared Firestore client used by the speaking-match service to
write real-time signalling documents for WebRTC call setup.

The Firebase app is initialised lazily on the first call to get_firestore()
and then reused for the lifetime of the process.
"""

from __future__ import annotations

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import settings

# Module-level reference to the initialised Firebase app.
# Set to None until first use.
_firebase_app: firebase_admin.App | None = None


def _init_firebase() -> firebase_admin.App:
    """
    Initialise the Firebase Admin SDK using the service-account JSON file
    specified by settings.FIREBASE_CREDENTIALS.

    Handles the case where the SDK has already been initialised (e.g. during
    hot-reload in development) by catching the ValueError raised by
    firebase_admin.initialize_app when a default app already exists.
    """
    try:
        # Load the service-account key from the path configured in settings.
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
        app = firebase_admin.initialize_app(cred)
        return app
    except ValueError:
        # The default app was already initialised — return the existing one.
        return firebase_admin.get_app()


def get_firestore() -> firestore.AsyncClient:
    """
    Return an async Firestore client, initialising Firebase if needed.

    Usage:
        fs = get_firestore()
        doc_ref = fs.collection("speaking_matches").document(doc_id)
        await doc_ref.set(data)
    """
    global _firebase_app

    # Initialise once and cache the app reference.
    if _firebase_app is None:
        _firebase_app = _init_firebase()

    # Return an async Firestore client bound to the initialised app.
    return firestore.AsyncClient(app=_firebase_app)
