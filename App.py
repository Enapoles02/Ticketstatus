import firebase_admin
from firebase_admin import credentials, firestore
import traceback

def test_firebase_connection():
    try:
        # 1. Cargar credenciales (ajusta si las tomas de st.secrets u otro JSON)
        cred_dict = {
            # copia aquí tu st.secrets["firebase_credentials"] o carga desde archivo
            "type": "...",
            "project_id": "...",
            # ...
        }
        cred = credentials.Certificate(cred_dict)
        print("🔑 Credentials loaded successfully")
        
        # 2. Inicializar app (si ya existe, omitir inicializar de nuevo)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
            print("🚀 Firebase app initialized")
        else:
            print("ℹ️ Firebase app already initialized")
        
        # 3. Crear cliente de Firestore
        db = firestore.client()
        print("📡 Firestore client created")
        
        # 4. Hacer una lectura de prueba
        doc = db.collection("aging_dashboard").document("latest_upload").get()
        print(f"📄 Documento 'latest_upload' existe? {doc.exists}")
        if doc.exists:
            data = doc.to_dict()
            print("🗂️ Ejemplo de contenido:", list(data.keys())[:5], "...")
        else:
            print("⚠️ El documento no existe aún (quizá nunca subiste datos)")
        
    except Exception as e:
        print("❌ Error en la conexión a Firebase:")
        traceback.print_exc()

if __name__ == "__main__":
    test_firebase_connection()
