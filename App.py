# ————————————————
# Debug Firebase (Streamlit)
# ————————————————
with st.expander("🔍 Debug Firebase Connection"):
    try:
        # 1) Obtener crendenciales desde st.secrets
        raw = st.secrets["firebase_credentials"]
        st.write("🔑 Credenciales cargadas:")
        st.json(raw)  # muestra solo las claves, no el private_key completo
        
        # 2) Inicializar app (si no está ya)
        if not firebase_admin._apps:
            cred_dbg = credentials.Certificate(raw)
            firebase_admin.initialize_app(cred_dbg)
            st.success("🚀 Firebase app initialized")
        else:
            st.info("ℹ️ Firebase app already initialized")
        
        # 3) Crear cliente Firestore y probar lectura
        db_dbg = firestore.client()
        st.success("📡 Firestore client created")
        
        doc = db_dbg.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
        st.write(f"📄 Document exists? {doc.exists}")
        if doc.exists:
            sample = doc.to_dict().get("data", [])[:3]
            st.write("🗂️ Sample data records:", sample)
        else:
            st.warning("⚠️ Document not found; quizás no has subido datos aún.")
    except Exception as e:
        st.error("❌ Firebase Debug Error:")
        st.text(str(e))
        import traceback
        st.text(traceback.format_exc())
