import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import traceback

def debug_firebase():
    with st.expander("🔍 Debug Firebase Connection"):
        try:
            # 1) Load credentials from secrets
            raw = st.secrets["firebase_credentials"]
            creds = json.loads(raw) if isinstance(raw, str) else raw

            # 2) Mask private_key in display
            masked = {k: ("***" if k == "private_key" else creds[k]) for k in creds}
            st.write("🔑 Credentials:", masked)

            # 3) Initialize Firebase app if not already
            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.Certificate(creds))
                st.success("🚀 Firebase app initialized")
            else:
                st.info("ℹ️ Firebase app already initialized")

            # 4) Create Firestore client and test read
            db = firestore.client()
            st.success("📡 Firestore client created")

            doc = db.collection("aging_dashboard").document("latest_upload").get()
            st.write("📄 Document exists?", doc.exists)
            if doc.exists:
                sample = doc.to_dict().get("data", [])[:3]
                st.write("🗂 Sample records:", sample)

        except Exception as e:
            st.error("❌ Firebase Debug Error:")
            st.text(str(e))
            st.text(traceback.format_exc())

# Run the debug routine
debug_firebase()
