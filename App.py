import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import traceback

# Ajusta esta ruta si tu JSON está en otro lugar
SERVICE_ACCOUNT_PATH = "/mnt/data/rewardschp-firebase-adminsdk-fbsvc-f636826040.json"
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"

def debug_firebase():
    with st.expander("🔍 Debug Firebase Connection"):
        try:
            # 1) Intentar cargar credenciales desde secrets
            raw = st.secrets.get("firebase_credentials")
            if raw is None:
                st.warning("⚠️ st.secrets['firebase_credentials'] no encontrada.")
                raise ValueError("No secrets")

            # Si viene como string JSON, parsearlo; si ya es dict, usarlo
            creds = json.loads(raw) if isinstance(raw, str) else raw
            
            # Mostrar keys (private_key enmascarada)
            masked = {k: ("***" if k=="private_key" else creds[k]) for k in creds}
            st.write("🔑 Secrets as dict:", masked)

            # 2) Intentar inicializar con dict
            try:
                firebase_admin.initialize_app(credentials.Certificate(creds))
                st.success("🚀 Firebase initialized using dict creds")
            except ValueError as e_dict:
                st.warning(f"❗ Failed initializing with dict: {e_dict}")

                # 3) Fallback: intentar usar el archivo JSON en disco
                try:
                    firebase_admin.initialize_app(credentials.Certificate(SERVICE_ACCOUNT_PATH))
                    st.success(f"🚀 Firebase initialized using file {SERVICE_ACCOUNT_PATH}")
                except Exception as e_file:
                    st.error(f"❌ Failed initializing with file: {e_file}")
                    st.text(traceback.format_exc())
                    return

            # 4) Crear cliente Firestore y probar lectura
            db = firestore.client()
            st.success("📡 Firestore client created")

            doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
            st.write("📄 Document exists?", doc.exists)
            if doc.exists:
                sample = doc.to_dict().get("data", [])[:3]
                st.write("🗂 Sample records:", sample)

        except Exception as e:
            st.error("⚠️ Unexpected debug error:")
            st.text(str(e))
            st.text(traceback.format_exc())

# LLama a la función en tu flujo de UI
debug_firebase()
