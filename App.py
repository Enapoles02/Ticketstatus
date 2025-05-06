import streamlit as st
import tempfile
import firebase_admin
from firebase_admin import credentials, firestore
import traceback

def inspect_key_bytes():
    # 1) Saca el dict puro del secreto
    creds_attr = st.secrets["firebase_credentials"]
    creds = creds_attr.to_dict() if hasattr(creds_attr, "to_dict") else creds_attr

    # 2) Extrae la clave y escríbela en un archivo .pem
    key = creds.get("private_key", "")
    tmp = tempfile.NamedTemporaryFile(delete=False, mode="wb", suffix=".pem")
    tmp.write(key.encode("utf-8"))
    tmp.flush()
    st.write(f"🛠 Clave escrita en: {tmp.name}")

    # 3) Lee los primeros bytes y muestra su repr()
    with open(tmp.name, "rb") as f:
        data = f.read()
    st.write("🔍 repr(bytes[:200]):", repr(data[:200]))

    # 4) Muestra las primeras 5 líneas (como repr) para ver espacios/BOM/CRLF
    lines = data.split(b"\n")
    for i, line in enumerate(lines[:5], 1):
        st.write(f"Linea {i} repr():", repr(line))

    # 5) Prueba limpiar cada línea (strip) y reconstruir la clave
    stripped = b"\n".join(l.strip() for l in lines) + b"\n"
    creds_clean = creds.copy()
    creds_clean["private_key"] = stripped.decode("utf-8")

    st.write("🔄 Intentando Certificate() con clave 'stripped'…")
    try:
        cert = credentials.Certificate(creds_clean)
        firebase_admin.initialize_app(cert)
        st.success("✅ Certificate aceptó la clave limpia")
        # Opcional: prueba Firestore
        db = firestore.client()
        doc = db.collection("aging_dashboard").document("latest_upload").get()
        st.write("📄 Document exists?", doc.exists)
    except Exception as e:
        st.error("❌ Sigue fallando tras strip:")
        st.text(str(e))
        st.text(traceback.format_exc())

st.button("🔍 Inspeccionar formato de private_key") and inspect_key_bytes()
