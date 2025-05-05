import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import traceback

def diagnose_firebase_secret():
    st.write("🔍 **Diagnóstico de `firebase_credentials`**")
    creds = st.secrets.get("firebase_credentials")
    st.write("**Tipo de secret:**", type(creds))
    
    if isinstance(creds, dict):
        st.write("**Claves disponibles:**", list(creds.keys()))
        private_key = creds.get("private_key", "")
        st.write("• ¿`private_key` es str?", isinstance(private_key, str))
        st.write("• Primeros 100 caracteres de `private_key`:", repr(private_key[:100]))
        st.write("• Número de saltos de línea en `private_key`:", private_key.count("\n"))
        st.write("• ¿Empieza con '-----BEGIN'?", private_key.strip().startswith("-----BEGIN"))
        st.write("• ¿Termina con 'END PRIVATE KEY-----'?", private_key.strip().endswith("-----END PRIVATE KEY-----"))
    else:
        st.write("**Valor completo de secret:**", repr(creds))

    st.write("\n🔍 **Intentando inicializar Firebase…**")
    try:
        cred = credentials.Certificate(creds)
        firebase_admin.initialize_app(cred)
        st.success("✅ Firebase inicializado sin errores")
    except Exception as e:
        st.error("❌ Error al crear Certificate o inicializar App:")
        st.text(str(e))
        st.text(traceback.format_exc())

# En tu flujo de Streamlit:
st.title("Debug Firebase")
if st.button("🔧 Diagnosticar Firebase"):
    diagnose_firebase_secret()
