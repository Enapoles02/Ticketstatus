# test_firebase.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json

# Título
st.title("🔎 Test de conexión a Firebase Firestore")

# Inicializar Firebase
if not firebase_admin._apps:
    firebase_credentials = json.loads(st.secrets["firebase_credentials"])
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Intentar leer el documento
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"

try:
    doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_ID)
    doc = doc_ref.get()
    if doc.exists:
        st.success("✅ Conexión a Firestore correcta.")
        st.subheader("Contenido del documento:")
        st.json(doc.to_dict())  # Mostrar el JSON bonito
    else:
        st.warning(f"⚠️ El documento `{DOCUMENT_ID}` no existe en la colección `{COLLECTION_NAME}`.")
except Exception as e:
    st.error(f"❌ Error al conectar o leer: {e}")
