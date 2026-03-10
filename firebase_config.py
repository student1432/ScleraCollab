"""
ScleraCollab — Firebase Configuration (Standalone)
Initialises Firebase Admin SDK using environment variables.
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
from dotenv import load_dotenv

load_dotenv()

def _init_firebase():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    try:
        # Option 1: path to service account JSON file
        sa_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
        if sa_path and os.path.exists(sa_path):
            print(f"Loading Firebase credentials from: {sa_path}")
            cred = credentials.Certificate(sa_path)

        # Option 2: inline JSON via env var (useful for Railway / Render / Heroku)
        elif os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'):
            print("Loading Firebase credentials from environment variable")
            sa_dict = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_JSON'])
            cred = credentials.Certificate(sa_dict)

        else:
            raise EnvironmentError(
                "No Firebase credentials found. "
                "Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_JSON."
            )

        bucket = os.environ.get('FIREBASE_STORAGE_BUCKET', '')
        firebase_admin.initialize_app(cred, {
            'storageBucket': bucket,
        })
        print("✅ Firebase initialized successfully")
        return firebase_admin.get_app()
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise


_init_firebase()

# Exported clients
db      = firestore.client()
fb_auth = auth            # firebase_admin.auth module
