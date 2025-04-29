import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

st.title("🔐 Firebase Connection Test")

# Validar si Firebase ya fue inicializado
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(st.secrets["firebase_credentials"])
        firebase_admin.initialize_app(cred)
        st.success("✅ Firebase initialized successfully.")
    except Exception as e:
        st.error(f"❌ Firebase initialization failed:\n\n{e}")

# Intentar conexión con Firestore
try:
    db = firestore.client()
    test_doc = db.collection("connection_test").document("ping")
    test_doc.set({"status": "connected"})
    result = test_doc.get()
    st.success(f"📡 Firestore test passed. Data: {result.to_dict()}")
except Exception as e:
    st.error(f"❌ Firestore test failed:\n\n{e}")
