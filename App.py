import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

st.title("🔐 Firebase Connection Test")

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(st.secrets["firebase_credentials"])
        firebase_admin.initialize_app(cred)
        st.success("✅ Firebase initialized successfully.")
except Exception as e:
    st.error(f"❌ Firebase initialization failed:\n\n{e}")

# Test Firestore connection
try:
    db = firestore.client()
    doc_ref = db.collection("connection_test").document("ping")
    doc_ref.set({"status": "connected"})
    result = doc_ref.get()
    st.success(f"📡 Firestore test passed. Data: {result.to_dict()}")
except Exception as e:
    st.error(f"❌ Firestore test failed:\n\n{e}")
