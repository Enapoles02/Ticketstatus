import streamlit as st
import json, tempfile
import firebase_admin
from firebase_admin import credentials, firestore

def compare_and_load():
    # 1) Carga el JSON original que subiste a /mnt/data
    try:
        with open("/mnt/data/rewardschp-firebase-adminsdk-fbsvc-f636826040.json", "r") as f:
            orig = json.load(f)
        st.write("✅ JSON original cargado.")
    except Exception as e:
        st.error(f"⚠️ No pude leer el JSON original: {e}")
        return

    # 2) Saca tu secreto de Streamlit y conviértelo a dict
    sec = st.secrets["firebase_credentials"]
    sec = sec.to_dict() if hasattr(sec, "to_dict") else sec

    # 3) Compara tamaños y primeros caracteres
    orig_key = orig.get("private_key", "")
    sec_key  = sec.get("private_key", "")
    st.write(f"🔑 Longitud de private_key en JSON original: {len(orig_key)}")
    st.write(f"🔑 Longitud de private_key en st.secrets:    {len(sec_key)}")
    st.write("🔍 Primeros 50 chars original:", repr(orig_key[:50]))
    st.write("🔍 Primeros 50 chars secret:   ", repr(sec_key[:50]))

    # 4) Escribe un archivo temporal a partir de sec y úsalo con Certificate()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    json.dump(sec, tmp)
    tmp.flush()
    st.write(f"🛠 Usando archivo temporal: {tmp.name}")

    try:
        cred = credentials.Certificate(tmp.name)
        firebase_admin.initialize_app(cred)
        st.success("🚀 Firebase inicializado correctamente (vía archivo temporal)")
        db = firestore.client()
        doc = db.collection("aging_dashboard").document("latest_upload").get()
        st.write("📄 Document exists?", doc.exists)
    except Exception as e:
        st.error("❌ Sigue fallando al inicializar:")
        st.text(str(e))

if st.button("🔧 Comparar y cargar credenciales"):
    compare_and_load()
