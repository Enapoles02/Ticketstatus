import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import traceback

# Constants for your Firestore collection/document
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"

def debug_firebase():
    with st.expander("🔍 Debug Firebase Connection"):
        try:
            # 1) Display loaded credential keys (masking private_key)
            raw = st.secrets["firebase_credentials"]
            masked = {k: ("***" if k == "private_key" else raw[k]) for k in raw}
            st.write("🔑 Credentials:", masked)

            # 2) Initialize Firebase app if needed
            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.Certificate(raw))
                st.success("🚀 Firebase app initialized")
            else:
                st.info("ℹ️ Firebase app already initialized")

            # 3) Create Firestore client and test read
            db_dbg = firestore.client()
            st.success("📡 Firestore client created")

            doc = db_dbg.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
            st.write(f"📄 Document exists? {doc.exists}")
            if doc.exists:
                sample = doc.to_dict().get("data", [])[:3]
                st.write("🗂️ Sample records:", sample)
        except Exception as e:
            st.error("❌ Firebase Debug Error:")
            st.text(str(e))
            st.text(traceback.format_exc())

# Run the debug on app start
debug_firebase()
