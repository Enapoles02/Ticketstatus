import streamlit as st
import pandas as pd
import io
import re
import uuid
import hashlib
import bcrypt
import qrcode
from datetime import datetime
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials, firestore

# -----------------------
# Configuración general
# -----------------------
st.set_page_config(page_title="Drop24 • Usuarios & QR", page_icon="🧺", layout="wide")

MEXICO_TZ = ZoneInfo("America/Mexico_City")
ADMIN_CODE = st.secrets.get("admin_code", "ADMIN")

# Firestore Collections
USERS_COL = "drop24_users"          # usuarios registrados
TOKENS_COL = "drop24_qr_tokens"     # QRs agendados

# Initialize Firebase only once (MISMA LÓGICA)
if not firebase_admin._apps:
    creds_attr = st.secrets["firebase_credentials"]
    creds = creds_attr.to_dict() if hasattr(creds_attr, "to_dict") else creds_attr
    cred = credentials.Certificate(creds)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -----------------------
# Helpers
# -----------------------
def now_cdmx():
    return datetime.now(MEXICO_TZ)

def now_cdmx_str():
    return now_cdmx().strftime("%Y-%m-%d %H:%M:%S %Z")

def normalize_phone(x: str) -> str:
    digits = re.sub(r"\D+", "", (x or "").strip())
    return digits

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def hash_password(pw: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw.encode("utf-8"), salt).decode("utf-8")

def check_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("utf-8"))
    except:
        return False

def make_token_id() -> str:
    # corto y robusto para QR
    return uuid.uuid4().hex[:12].upper()

def make_qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()

def user_doc(username: str):
    return db.collection(USERS_COL).document(username)

def token_doc(token_id: str):
    return db.collection(TOKENS_COL).document(token_id)

def parse_dt(date_obj, time_obj) -> datetime:
    # date_input devuelve date, time_input devuelve time
    dt_naive = datetime.combine(date_obj, time_obj)
    # convertir a tz CDMX (naive -> aware)
    return dt_naive.replace(tzinfo=MEXICO_TZ)

def require_fields(d: dict, fields: list[str]) -> list[str]:
    missing = []
    for f in fields:
        v = d.get(f)
        if v is None or str(v).strip() == "":
            missing.append(f)
    return missing

# -----------------------
# Session
# -----------------------
if "auth" not in st.session_state:
    st.session_state.auth = False
if "username" not in st.session_state:
    st.session_state.username = None

# -----------------------
# UI
# -----------------------
st.title("🧺 Drop24 • Registro, Login & QR Agendado")
st.caption("Registro abierto para usuarios. Genera QRs con ventana de tiempo y valida en app Android.")

tab_login, tab_register, tab_qr = st.tabs(["🔐 Login", "📝 Registro", "📲 Generar QR (agendado)"])

# -----------------------
# LOGIN
# -----------------------
with tab_login:
    st.subheader("🔐 Login")
    col1, col2 = st.columns([1, 1])

    with col1:
        username = st.text_input("Usuario", placeholder="ej: enapoles")
        password = st.text_input("Contraseña", type="password")

        if st.button("Ingresar"):
            u = (username or "").strip().lower()
            if not u or not password:
                st.error("Completa usuario y contraseña.")
            else:
                doc = user_doc(u).get()
                if not doc.exists:
                    st.error("Usuario no existe.")
                else:
                    data = doc.to_dict()
                    if not data.get("active", True):
                        st.error("Usuario desactivado. Contacta a ADMIN.")
                    elif not check_password(password, data.get("password_hash", "")):
                        st.error("Contraseña incorrecta.")
                    else:
                        st.session_state.auth = True
                        st.session_state.username = u
                        st.success(f"Bienvenido: {u} ✅")
                        st.rerun()

    with col2:
        st.info(
            "Tip: si quieres que solo ADMIN pueda aprobar usuarios, "
            "puedo agregarte un flujo de estatus (PENDING → ACTIVE)."
        )

    st.divider()
    if st.session_state.auth:
        st.success(f"Sesión activa: {st.session_state.username}")
        if st.button("Cerrar sesión"):
            st.session_state.auth = False
            st.session_state.username = None
            st.rerun()

# -----------------------
# REGISTRO
# -----------------------
with tab_register:
    st.subheader("📝 Registro de usuario (campos obligatorios)")

    with st.form("register_form", clear_on_submit=False):
        username_r = st.text_input("Usuario (único)", placeholder="ej: drop24_user1").strip().lower()
        pw1 = st.text_input("Contraseña", type="password")
        pw2 = st.text_input("Confirmar contraseña", type="password")

        c1, c2, c3 = st.columns(3)
        with c1:
            full_name = st.text_input("Nombre completo *")
        with c2:
            phone = st.text_input("Teléfono (WhatsApp) *")
        with c3:
            email = st.text_input("Email *")

        
        st.markdown("### Ubicación")
        c7, c8 = st.columns(2)
        with c7:
            neighborhood = st.text_input("Colonia/Alcaldía *", placeholder="Coapa / Coyoacán / etc.")
        with c8:
            address_ref = st.text_input("Referencia (opcional)", placeholder="cerca de…")

        consent_gps = st.checkbox("Consentimiento para guardar GPS (opcional)", value=False)
        gps_lat = st.text_input("Latitud (opcional)", disabled=not consent_gps)
        gps_lon = st.text_input("Longitud (opcional)", disabled=not consent_gps)

        submitted = st.form_submit_button("Crear cuenta")

    if submitted:
        # Validaciones
        payload = {
            "username": username_r,
            "full_name": full_name.strip(),
            "phone": normalize_phone(phone),
            "email": email.strip().lower(),
            "ine_last4": (ine_last4 or "").strip(),
            "ine_verified": bool(ine_verified),
            "neighborhood": neighborhood.strip(),
            "address_ref": address_ref.strip(),
        }

        required = ["username", "full_name", "phone", "email", "ine_last4", "neighborhood"]
        missing = require_fields(payload, required)
        if missing:
            st.error(f"Faltan campos obligatorios: {', '.join(missing)}")
        elif len(payload["ine_last4"]) != 4 or not payload["ine_last4"].isdigit():
            st.error("INE últimos 4 debe ser numérico de 4 dígitos.")
        elif not payload["phone"]:
            st.error("Teléfono inválido.")
        elif pw1 != pw2:
            st.error("Las contraseñas no coinciden.")
        elif len(pw1) < 6:
            st.error("Contraseña muy corta (mínimo 6).")
        elif not ine_verified:
            st.error("Debes marcar INE verificada (si quieres, luego lo cambiamos a flujo de aprobación).")
        else:
            # Hash de INE (si el usuario insiste en capturarla)
            # Recomendación: NO usar esto. Si lo usan, solo guardamos HASH.
            ine_hash = None
            if ine_hash_input and ine_hash_input.strip():
                ine_hash = sha256_hex(ine_hash_input.strip())

            # GPS opcional
            gps = None
            if consent_gps and gps_lat.strip() and gps_lon.strip():
                gps = {"lat": gps_lat.strip(), "lon": gps_lon.strip()}

            doc_ref = user_doc(username_r)
            if doc_ref.get().exists:
                st.error("Ese usuario ya existe. Elige otro.")
            else:
                doc_ref.set({
                    "username": username_r,
                    "password_hash": hash_password(pw1),
                    "full_name": payload["full_name"],
                    "phone": payload["phone"],
                    "email": payload["email"],
                    "ine_last4": payload["ine_last4"],
                    "ine_hash": ine_hash,            # solo hash, nunca el número en claro
                    "ine_verified": payload["ine_verified"],
                    "neighborhood": payload["neighborhood"],
                    "address_ref": payload["address_ref"],
                    "gps": gps,
                    "active": True,
                    "role": "USER",
                    "created_at": now_cdmx_str(),
                })
                st.success("Cuenta creada ✅ Ya puedes ir a Login e ingresar.")

# -----------------------
# GENERAR QR (agendado)
# -----------------------
with tab_qr:
    st.subheader("📲 Generar QR (agendado)")

    if not st.session_state.auth:
        st.info("Primero inicia sesión para generar QRs.")
        st.stop()

    st.success(f"Sesión: {st.session_state.username}")

    # Inputs del QR
    c1, c2, c3 = st.columns(3)
    with c1:
        client_id = st.text_input("Client ID (de tu base)", placeholder="CNA1234....")
    with c2:
        access_type = st.selectbox("Qué abre este QR", ["BZ (Buzón)", "L1 (Locker 1)", "L2 (Locker 2)"])
    with c3:
        one_time = st.checkbox("QR de 1 solo uso (recomendado)", value=True)

    st.markdown("### Ventana de tiempo (CDMX)")
    d1, t1, d2, t2 = st.columns([1,1,1,1])
    with d1:
        start_date = st.date_input("Inicio (fecha)", value=now_cdmx().date())
    with t1:
        start_time = st.time_input("Inicio (hora)", value=now_cdmx().time().replace(second=0, microsecond=0))
    with d2:
        end_date = st.date_input("Fin (fecha)", value=now_cdmx().date())
    with t2:
        end_time = st.time_input("Fin (hora)", value=(now_cdmx().time().replace(second=0, microsecond=0)))

    prefix = st.text_input("Prefijo QR", value="DROP24")

    if st.button("✅ Crear QR"):
        if not client_id.strip():
            st.error("Client ID es obligatorio.")
        else:
            start_dt = parse_dt(start_date, start_time)
            end_dt = parse_dt(end_date, end_time)
            if end_dt <= start_dt:
                st.error("La hora fin debe ser mayor a la hora inicio.")
            else:
                token_id = make_token_id()
                payload = f"{prefix}|{token_id}"  # QR corto, la app valida en Firestore

                # Guardar en Firestore
                token_doc(token_id).set({
                    "token_id": token_id,
                    "payload": payload,
                    "client_id": client_id.strip(),
                    "access_type": access_type.split()[0],  # BZ / L1 / L2
                    "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "one_time": bool(one_time),
                    "used": False,
                    "used_at": None,
                    "created_by": st.session_state.username,
                    "created_at": now_cdmx_str(),
                    "active": True
                })

                # QR PNG
                png = make_qr_png_bytes(payload)

                st.success("QR creado y guardado ✅")
                st.code(payload)

                st.image(png, caption="QR generado", width=260)
                st.download_button(
                    "⬇️ Descargar QR (PNG)",
                    data=png,
                    file_name=f"DROP24_QR_{token_id}.png",
                    mime="image/png"
                )

    st.divider()
    st.markdown("### Últimos QRs generados (para control)")
    # Mostrar últimos 20
    docs = db.collection(TOKENS_COL).order_by("created_at", direction=firestore.Query.DESCENDING).limit(20).stream()
    rows = []
    for d in docs:
        dd = d.to_dict()
        rows.append({
            "token_id": dd.get("token_id"),
            "client_id": dd.get("client_id"),
            "access_type": dd.get("access_type"),
            "start_time": dd.get("start_time"),
            "end_time": dd.get("end_time"),
            "one_time": dd.get("one_time"),
            "used": dd.get("used"),
            "created_by": dd.get("created_by"),
            "created_at": dd.get("created_at"),
            "active": dd.get("active"),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay QRs.")
