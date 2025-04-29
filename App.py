import streamlit as st
import firebase_admin
from firebase_admin import credentials
import json

st.title("🔎 Firebase Debugging")

# Mostrar qué está leyendo exactamente
st.subheader("🔍 Raw st.secrets[\"firebase_credentials\"]")

try:
    raw = st.secrets["firebase_credentials"]
    st.write(raw)
    st.success("✅ Successfully read st.secrets[\"firebase_credentials\"]")
except Exception as e:
    st.error(f"❌ Failed to read st.secrets: {e}")

# Intentar ver si es dict o string
st.subheader("📚 Type of st.secrets[\"firebase_credentials\"]")

try:
    st.write(f"Type: {type(raw)}")
except Exception as e:
    st.error(f"❌ Failed to get type: {e}")

# Intentar inicializar Firebase
st.subheader("🚀 Firebase initialization test")

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(raw)
        firebase_admin.initialize_app(cred)
        st.success("✅ Firebase initialized successfully.")
except Exception as e:
    st.error(f"❌ Firebase initialization failed: {e}")
