import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="🔐 Firebase Test", layout="centered")
st.title("🔐 Firebase Connection Test")

# 1. Leer secretos
try:
    firebase_secret = dict(st.secrets["firebase_credentials"])
    firebase_secret["private_key"] = firebase_secret["private_key"].replace("\\n", "\n")
    st.success("✅ Loaded and formatted firebase_credentials")
except Exception as e:
    st.error(f"❌ Failed to load firebase_credentials: {e}")
    st.stop()

# 2. Mostrar tipo y claves
st.subheader("📚 Type of firebase_credentials")
st.code(str(type(firebase_secret)))
st.subheader("🔑 Keys in firebase_credentials")
st.code(list(firebase_secret.keys()))

# 3. Inicializar Firebase
st.subheader("🚀 Firebase Initialization")
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_secret)
        firebase_admin.initialize_app(cred)
        st.success("✅ Firebase initialized successfully!")
    else:
        st.info("ℹ️ Firebase already initialized.")
except Exception as e:
    st.error(f"❌ Firebase initialization failed:\n\n{e}")
    st.stop()

# 4. Probar conexión a Firestore
st.subheader("🧪 Firestore Test")
try:
    db = firestore.client()
    test_doc = db.collection("test_connection").document("streamlit_test")
    test_doc.set({
        "status": "connected via Streamlit",
        "success": True
    })
    doc = test_doc.get()
    st.success("✅ Firestore write and read successful!")
    st.code(doc.to_dict())
except Exception as e:
    st.error(f"❌ Firestore test failed:\n\n{e}")
