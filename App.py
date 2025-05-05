import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import traceback

def inspect_and_fix_key():
    # 1) Obtén el AttrDict y conviértelo a dict
    creds_attr = st.secrets["firebase_credentials"]
    creds = creds_attr.to_dict() if hasattr(creds_attr, "to_dict") else creds_attr

    # 2) Extrae el private_key y muestra su contenido crudo
    key = creds.get("private_key", "")
    st.write("📋 repr(private_key):", repr(key))
    st.write("🔢 Saltos de línea reales:", key.count("\n"))
    st.write("🔢 Secuencias literales '\\n':", key.count("\\n"))

    # 3) Si hay '\n' literales, los convertimos a saltos de línea reales
    if "\\n" in key:
        st.info("⚙️ Detectadas secuencias '\\n', convirtiendo a saltos reales")
        key = key.replace("\\n", "\n")
        creds["private_key"] = key

    st.write("🔄 Tras conversión, saltos de línea reales:", key.count("\n"))

    # 4) Intento de crear el Certificate y mostrar stack si falla
    try:
        cert = credentials.Certificate(creds)
        st.success("✅ credentials.Certificate aceptó el dict")
        # (opcional) inicializas la app y pruebas Firestore
        firebase_admin.initialize_app(cert)
        db = firestore.client()
        doc = db.collection("aging_dashboard").document("latest_upload").get()
        st.write("📄 Document exists?", doc.exists)
    except Exception as e:
        st.error("❌ Error al crear Certificate o inicializar:")
        st.text(str(e))
        st.text(traceback.format_exc())

st.button("🔍 Inspeccionar y arreglar private_key") and inspect_and_fix_key()
