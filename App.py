import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import traceback

def diagnose_and_fix_firebase():
    st.write("🔍 **Diagnóstico de `firebase_credentials`**")
    creds = st.secrets["firebase_credentials"]
    st.write("• Tipo original de `creds`:", type(creds))

    if hasattr(creds, "to_dict"):
        creds_dict = creds.to_dict()
        st.write("• Tras `to_dict()`, tipo:", type(creds_dict))
    else:
        creds_dict = creds
        st.write("• No había `to_dict()`, usamos `creds` directo")

    st.write("🔍 **Intentando inicializar con el dict puro…**")
    try:
        # Aquí es donde antes fallaba si pasabas el AttrDict
        cert = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cert)
        st.success("✅ Firebase inicializado CORRECTAMENTE usando `to_dict()`")
        
        # Prueba rápida de Firestore
        db = firestore.client()
        doc = db.collection("aging_dashboard").document("latest_upload").get()
        st.write("📄 Document exists?", doc.exists)
    except Exception as e:
        st.error("❌ Sigue fallando al inicializar:")
        st.text(str(e))
        st.text(traceback.format_exc())

st.title("Diagnóstico y Corrección Firebase")
if st.button("🔧 Diagnosticar y Corregir"):
    diagnose_and_fix_firebase()
