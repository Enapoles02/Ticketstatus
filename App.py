import streamlit as st
from firebase_admin import credentials
import inspect

def why_certificate_fails():
    creds = st.secrets["firebase_credentials"]
    
    st.write("1. Tipo de `creds`:", type(creds))
    st.write("2. ¿`isinstance(creds, dict)`?", isinstance(creds, dict))
    st.write("3. ¿`issubclass(type(creds), dict)`?", issubclass(type(creds), dict))
    st.write("4. ¿Tiene método `to_dict`?", hasattr(creds, "to_dict"))
    
    if hasattr(creds, "to_dict"):
        plain = creds.to_dict()
        st.write("5. Tras `creds.to_dict()`, tipo:", type(plain))
        st.write("   Claves:", list(plain.keys()))
    
    st.write("6. Firma de Certificate():", inspect.signature(credentials.Certificate))
    
    try:
        # Intento directo: esto es lo que falla
        credentials.Certificate(creds)
        st.success("✅ Esta línea NO debería llegar si `creds` no es dict")
    except Exception as e:
        st.error("❌ Aquí está el error al llamar a Certificate():")
        st.text(str(e))

st.button("🔍 ¿Por qué falla Certificate?") and why_certificate_fails()
