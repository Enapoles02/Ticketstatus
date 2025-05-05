import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import ast
import traceback

def debug_firebase():
    with st.expander("🔍 Debug Firebase Connection"):
        try:
            raw = st.secrets["firebase_credentials"]
            # Si viene como string, intentar JSON, si falla, literal_eval
            if isinstance(raw, str):
                try:
                    creds = json.loads(raw)
                    st.info("Parsed secrets as JSON")
                except json.JSONDecodeError:
                    creds = ast.literal_eval(raw)
                    st.info("Parsed secrets via literal_eval")
            else:
                creds = raw
                st.info("Secrets already a dict")

            # Mostrar keys (ocultar private_key)
            masked = {k: ("***" if k == "private_key" else creds[k]) for k in creds}
            st.write("🔑 Credentials dict:", masked)

            # Inicializar app
            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.Certificate(creds))
                st.success("🚀 Firebase initialized with dict creds")
            else:
                st.info("ℹ️ Firebase app already initialized")

            # Firestore client y prueba
            db = firestore.client()
            st.success("📡 Firestore client created")
            doc = db.collection("aging_dashboard").document("latest_upload").get()
            st.write("📄 Document exists?", doc.exists)
            if doc.exists:
                st.write("🗂 Sample data:", doc.to_dict().get("data", [])[:3])

        except Exception as e:
            st.error("❌ Firebase Debug Error:")
            st.text(str(e))
            st.text(traceback.format_exc())

debug_firebase()
