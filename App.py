import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import uuid
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import re
import io

import qrcode
import bcrypt
import streamlit.components.v1 as components

# =================================================
# BRANDING / CONFIG (Drop24)
# =================================================
# OPCIÓN A (recomendado): sube tu logo local (assets/drop24_logo.png)
# OPCIÓN B: usa URL en secrets drop24_logo_url
LOGO_URL = st.secrets.get("drop24_logo_url", "").strip()  # opcional

ORG_NAME = "DROP24"
ORG_SUB = "Lavandería inteligente · Registro · QR Agendado · Servicio a domicilio (próximamente)"

# Paleta estilo
C_TEAL_DARK = "#055671"
C_TEAL_MID = "#6699A5"
C_CYAN_LIGHT = "#B4DFE8"
C_BG = "#F9FAF8"
C_TEXT_MUTED = "#6A7067"

# =================================================
# STREAMLIT CONFIG
# =================================================
st.set_page_config(
    page_title="Drop24 · Usuarios & QR",
    page_icon="🧺",
    layout="wide",
)

MEXICO_TZ = ZoneInfo("America/Mexico_City")

# =================================================
# CSS (MISMO ESTILO)
# =================================================
st.markdown(
    f"""
    <style>
    body {{
        background-color: {C_BG};
        font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
        color: #0B1F2A;
    }}

    .corp-header {{
        width: 100%;
        background: linear-gradient(90deg, {C_TEAL_DARK} 0%, {C_TEAL_MID} 55%, {C_CYAN_LIGHT} 100%);
        color: white;
        padding: 14px 26px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 12px rgba(0,0,0,0.18);
        margin-bottom: 18px;
        border-radius: 0 0 18px 18px;
        position: relative;
        overflow: hidden;
    }}

    .corp-header::after {{
        content: "";
        position: absolute;
        top: 0;
        left: -20%;
        width: 140%;
        height: 100%;
        background: radial-gradient(circle at 80% 50%, rgba(255,255,255,0.85) 0%, rgba(180,223,232,0.35) 30%, rgba(5,86,113,0) 70%);
        opacity: 0.55;
        transform: skewX(-18deg);
    }}

    .corp-header-left {{
        display: flex;
        align-items: center;
        gap: 14px;
        position: relative;
        z-index: 2;
        max-width: 75%;
    }}

    .corp-logo {{
        height: 44px;
        width: auto;
        border-radius: 10px;
        background: rgba(255,255,255,0.92);
        padding: 6px 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    }}

    .corp-header-title {{
        font-size: 14px;
        font-weight: 900;
        color: #FFFFFF;
        line-height: 1.15;
        text-transform: uppercase;
    }}

    .corp-header-sub {{
        font-size: 12px;
        opacity: 0.95;
        color: #EAF7FB;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }}

    .corp-header-right {{
        font-size: 12px;
        text-align: right;
        position: relative;
        z-index: 2;
        color: #FFFFFF;
        opacity: 0.98;
        min-width: 190px;
    }}

    .big-title {{
        font-size: 30px;
        font-weight: 900;
        text-align: center;
        margin-bottom: 4px;
        color: {C_TEAL_DARK};
    }}

    .subtitle {{
        font-size: 14px;
        text-align: center;
        color: {C_TEXT_MUTED};
        margin-bottom: 18px;
    }}

    .card {{
        background-color: #FFFFFF;
        border-left: 6px solid {C_TEAL_DARK};
        border-radius: 16px;
        padding: 14px 16px;
        margin: 8px 0;
        color: #0B1F2A;
        box-shadow: 0 4px 14px rgba(0,0,0,0.06);
    }}

    .pill {{
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        background-color: #EAF7FB;
        color: {C_TEAL_DARK};
        font-size: 12px;
        margin: 3px;
        border: 1px solid {C_CYAN_LIGHT};
        font-weight: 800;
    }}

    .note {{
        color: {C_TEXT_MUTED};
        font-size: 12px;
    }}

    /* Botones */
    .stButton > button {{
        border-radius: 12px !important;
        border: 1px solid {C_CYAN_LIGHT} !important;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: #FFFFFF;
        border-right: 1px solid rgba(0,0,0,0.06);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)



# =================================================
# FIREBASE (NO TOCAR)
# =================================================
@st.cache_resource
def init_firebase():
    firebase_creds = st.secrets["firebase_credentials"]
    if hasattr(firebase_creds, "to_dict"):
        firebase_creds = firebase_creds.to_dict()

    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_creds)
        firebase_admin.initialize_app(cred)

    return firestore.client()

db = init_firebase()

# =================================================
# SECRETS
# =================================================
ADMIN_CODE = st.secrets.get("admin_code", "ADMIN")

# =================================================
# COLLECTIONS
# =================================================
USERS_COL = "drop24_users"
TOKENS_COL = "drop24_qr_tokens"

# =================================================
# HELPERS
# =================================================
def now_mx():
    return datetime.now(MEXICO_TZ)

def now_mx_str():
    return now_mx().strftime("%Y-%m-%d %H:%M:%S %Z")

def normalize_phone(x: str) -> str:
    return re.sub(r"\D+", "", (x or "").strip())

def hash_password(pw: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw.encode("utf-8"), salt).decode("utf-8")

def check_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("utf-8"))
    except Exception:
        return False

def user_ref(username: str):
    return db.collection(USERS_COL).document(username)

def token_ref(token_id: str):
    return db.collection(TOKENS_COL).document(token_id)

def make_token_id() -> str:
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

def dt_to_str(dt: datetime) -> str:
    return dt.astimezone(MEXICO_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

def require_fields(data: dict, required: list[str]) -> list[str]:
    return [k for k in required if not str(data.get(k, "")).strip()]

def is_admin():
    entered = (st.session_state.get("admin_code_value", "") or "").strip()
    return entered == (ADMIN_CODE or "").strip()

# =================================================
# QR SECURITY HELPERS (NUEVO)
# =================================================
def get_active_qr_for_user(username: str):
    """Regresa el token más reciente del usuario que siga activo y vigente (end_ts > now)."""
    now_dt = now_mx()

    docs = (
        db.collection(TOKENS_COL)
        .where("created_by", "==", username)
        .limit(50)
        .stream()
    )

    best = None
    best_created = ""

    for d in docs:
        x = d.to_dict() or {}

        if not x.get("active", False):
            continue

        if x.get("one_time", False) and x.get("used", False):
            continue

        end_ts = x.get("end_ts")
        if not end_ts or not isinstance(end_ts, datetime):
            continue

        # Asegura timezone CDMX si viene naive
        if end_ts.tzinfo is None:
            end_ts = end_ts.replace(tzinfo=MEXICO_TZ)

        if end_ts > now_dt:
            ca = x.get("created_at", "")
            if ca >= best_created:
                best = d
                best_created = ca

    return best

# =================================================
# LOCKER SLOTS (HORA) - REQUIRED
# =================================================
def next_full_hour_slots(start_hour=7, end_hour=21):
    """
    Devuelve slots de 1 hora en formato 24h:
    07:00-08:00, 08:00-09:00, ... , 20:00-21:00
    end_hour es el fin (no incluido).
    """
    return [f"{h:02d}:00-{h+1:02d}:00" for h in range(start_hour, end_hour)]


def slot_to_datetimes(slot_label: str, day_date):
    """
    Convierte '19:00-20:00' + date -> start_dt, end_dt (timezone CDMX)
    """
    a, b = slot_label.split("-")
    sh, sm = map(int, a.split(":"))
    eh, em = map(int, b.split(":"))
    start_dt = datetime.combine(day_date, dtime(sh, sm)).replace(tzinfo=MEXICO_TZ)
    end_dt = datetime.combine(day_date, dtime(eh, em)).replace(tzinfo=MEXICO_TZ)
    return start_dt, end_dt


def slot_to_display(slot_label: str) -> str:
    """
    '19:00-20:00' -> '7:00 PM - 8:00 PM'
    (solo visual, el value real sigue siendo 24h)
    """
    a, b = slot_label.split("-")

    def _fmt(x):
        h, m = map(int, x.split(":"))
        ampm = "AM" if h < 12 else "PM"
        hh = h % 12
        if hh == 0:
            hh = 12
        return f"{hh}:{m:02d} {ampm}"

    return f"{_fmt(a)} - {_fmt(b)}"


# =================================================
# PRECIOS DROP24 (EDITA AQUÍ)
# =================================================
PRICES = {
    # AUTOSERVICIO
    "lavado_carga_completa": 90,     # hasta 22 kg
    "secado_30_min": 40,
    "secado_15_extra": 20,
    "secado_60_min": 80,

    # DROP EXPRESS (MOSTRADOR)
    "lavado_secado_por_kg": 32,
    "promo_15kg": 420,

    # BUZÓN 24/7
    "buzon_por_kg": 34,
    "locker_24_7": 30,              # renta locker por servicio (recolección 24/7)

    # ESPECIALES (por pieza)
    "edredon_ind_matr": 160,
    "edredon_q_king": 190,
}


# ---------------------------
# CHATBOT HELPERS
# ---------------------------
def drop24_help_answer(user_text: str) -> str:
    t = (user_text or "").lower().strip()
    p = PRICES

    # --- PRECIOS ---
    if any(k in t for k in ["precio", "precios", "cuánto", "cuanto", "costo", "vale", "$", "tarifa"]):
        return (
            "💸 **Precios Drop24**\n\n"
            "### 🧺 Autoservicio\n"
            f"- Lavado (carga completa hasta 22 kg): **${p['lavado_carga_completa']}**\n"
            f"- Secado 30 min: **${p['secado_30_min']}**\n"
            f"- 15 min extra: **${p['secado_15_extra']}**\n"
            f"- 60 min: **${p['secado_60_min']}**\n\n"
            "📌 *El precio es por ciclo de lavadora, no por kilo.*\n"
            "📌 *El cliente trae sus insumos (o puede adquirirlos en mostrador).*\n\n"
            "### 🧺 Drop Express (Mostrador)\n"
            "📌 Política: entrega en 24 horas hábiles (sujeto a disponibilidad) · doblado básico incluido.\n"
            f"- Lavado + Secado: **${p['lavado_secado_por_kg']} por kilo**\n"
            f"- Promoción (15 kg): **${p['promo_15kg']}**\n"
            "📌 *Incluye detergente premium y suavizante.*\n"
            "📌 *Se pesa al recibir. Mínimo de cobro: 3 kg.*\n\n"
            "### 📦 Buzón inteligente 24/7\n"
            f"- Ropa general: **${p['buzon_por_kg']} por kilo**\n"
            f"- Renta de locker (por servicio) / Recolección 24/7: **${p['locker_24_7']}**\n\n"
            "### 🛏️ Especiales (por pieza)\n"
            f"- Edredones y cobijas (Individual/Matrimonial): **${p['edredon_ind_matr']}**\n"
            f"- Edredones y cobijas (Queen/King): **${p['edredon_q_king']}**\n\n"
            "Si me dices qué vas a lavar (kg o piezas), te calculo el total ✅"
        )

    # --- BUZÓN ---
    if any(k in t for k in ["buzon", "buzón", "24/7", "depositar", "dejar ropa"]):
        return (
            "🧺 **Buzón 24/7 (Drop24)**\n\n"
            "1) Te registras en mostrador y obtienes tu **QR**.\n"
            "2) Escaneas el QR en el buzón.\n"
            "3) La puerta se libera y depositas tu ropa en bolsa/morral identificado.\n"
            "4) Recolectamos en el siguiente horario hábil y comenzamos el proceso.\n\n"
            f"Precio ropa general: **${p['buzon_por_kg']} por kilo**\n"
            f"Renta de locker (por servicio) / Recolección 24/7: **${p['locker_24_7']}**"
        )

    # --- ENTREGA ---
    if any(k in t for k in ["tarda", "entrega", "cuando", "listo", "24 horas", "24hrs", "24 h"]):
        return (
            "⏱️ **Tiempos de entrega**\n\n"
            "En Drop Express (Mostrador): **Entrega en 24 horas hábiles** (sujeto a disponibilidad).\n"
            "Si es volumen grande o prendas especiales, puede variar.\n\n"
            "Dime cuántos kg o si incluye edredón/cobija y te doy un estimado."
        )

    # --- QR ---
    if any(k in t for k in ["qr", "token", "agendado", "ventana", "no funciona", "error"]):
        return (
            "📲 **Problemas con tu QR (Checklist)**\n\n"
            "1) Verifica que estás dentro de la **ventana de tiempo**.\n"
            "2) Si era de **1 uso**, revisa que no esté marcado como **used**.\n"
            "3) Confirma el acceso correcto: **BZ / L1 / L2**.\n\n"
            "Si me dices qué mensaje te sale o qué estás intentando abrir, te digo exactamente qué revisar."
        )

    # --- DEFAULT ---
    return (
        "¡Claro! 🙌\n\n"
        "Escribe una opción o tu duda:\n"
        "1) **Precios**\n"
        "2) **Buzón 24/7**\n"
        "3) **QR agendado**\n"
        "4) **Tiempos de entrega**\n"
        "5) **Especiales (edredones/cobijas)**\n"
    )


def send_to_drop24_bot(text: str):
    if not text:
        return
    if "drop24_chat" not in st.session_state:
        st.session_state.drop24_chat = [
            {"role": "assistant", "content": "¡Hola! Soy el asistente de Drop24 🧺 ¿Qué duda tienes hoy?"}
        ]
    st.session_state.drop24_chat.append({"role": "user", "content": text})
    reply = drop24_help_answer(text)
    st.session_state.drop24_chat.append({"role": "assistant", "content": reply})
    st.rerun()


# =================================================
# SESSION
# =================================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "username" not in st.session_state:
    st.session_state.username = None

# =================================================
# LOGO HTML (URL o fallback)
# =================================================
logo_html = (
    f"""<img class="corp-logo" src="{LOGO_URL}" />"""
    if LOGO_URL
    else """<div class="corp-logo" style="display:flex;align-items:center;justify-content:center;font-weight:900;color:#055671;">DROP24</div>"""
)

# =================================================
# HEADER
# =================================================
st.markdown(
    f"""
    <div class="corp-header">
        <div class="corp-header-left">
            {logo_html}
            <div>
                <div class="corp-header-title">{ORG_NAME}</div>
                <div class="corp-header-sub">{ORG_SUB}</div>
            </div>
        </div>
        <div class="corp-header-right">
            <div><b>Portal de Usuarios</b></div>
            <div style="opacity:0.92;">Registro · Login · QR agendado</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div class='big-title'>Drop24 · Usuarios & QR</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Registro de clientes y domicilio para servicio a domicilio (próximamente)</div>", unsafe_allow_html=True)

st.markdown("---")

with st.container():
    colL, colR = st.columns([2, 3], vertical_alignment="center")

    # IZQUIERDA: estado sesión
    with colL:
        if st.session_state.auth and st.session_state.username:
            st.success(f"✅ Sesión activa: {st.session_state.username}")
            if st.button("Cerrar sesión", use_container_width=True, key="btn_logout_top"):
                st.session_state.auth = False
                st.session_state.username = None
                st.rerun()
        else:
            st.info("🔐 Inicia sesión para generar QRs y usar funciones avanzadas.")

    # DERECHA: formulario login
    with colR:
        expanded_login = not (st.session_state.auth and st.session_state.username)
        with st.expander("👤 Login", expanded=expanded_login):
            u_in = st.text_input("Usuario", value=st.session_state.get("username") or "", key="login_user_top")
            p_in = st.text_input("Contraseña", type="password", key="login_pass_top")

            if st.button("Ingresar", use_container_width=True, key="btn_login_top"):
                u = (u_in or "").strip().lower()
                if not u or not p_in:
                    st.error("Completa usuario y contraseña.")
                else:
                    doc = user_ref(u).get()
                    if not doc.exists:
                        st.error("Usuario no existe.")
                    else:
                        data = doc.to_dict() or {}
                        if not data.get("active", True):
                            st.error("Usuario desactivado. Contacta a Drop24.")
                        elif not check_password(p_in, data.get("password_hash", "")):
                            st.error("Contraseña incorrecta.")
                        else:
                            st.session_state.auth = True
                            st.session_state.username = u
                            st.success(f"Bienvenido(a), {data.get('full_name','')} ✅")
                            st.rerun()

st.markdown("---")


# =================================================
# SIDEBAR (LOGIN + ADMIN)
# =================================================
st.sidebar.title("🔐 Accesos")

with st.sidebar.expander("👤 Login Usuario", expanded=True):
    u_in = st.text_input("Usuario", value=st.session_state.get("username") or "", key="login_user")
    p_in = st.text_input("Contraseña", type="password", key="login_pass")

    if st.button("Ingresar", use_container_width=True, key="btn_login"):
        u = (u_in or "").strip().lower()
        if not u or not p_in:
            st.error("Completa usuario y contraseña.")
        else:
            doc = user_ref(u).get()
            if not doc.exists:
                st.error("Usuario no existe.")
            else:
                data = doc.to_dict() or {}
                if not data.get("active", True):
                    st.error("Usuario desactivado. Contacta a Drop24.")
                elif not check_password(p_in, data.get("password_hash", "")):
                    st.error("Contraseña incorrecta.")
                else:
                    st.session_state.auth = True
                    st.session_state.username = u
                    st.success(f"Bienvenido(a), {data.get('full_name','')} ✅")
                    st.rerun()

    if st.session_state.auth and st.session_state.username:
        st.caption(f"Sesión: **{st.session_state.username}**")
        if st.button("Cerrar sesión", use_container_width=True, key="btn_logout"):
            st.session_state.auth = False
            st.session_state.username = None
            st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("🛡️ Admin (solo para control)", expanded=False):
    st.text_input("Código admin", type="password", key="admin_code_value")
    if is_admin():
        st.success("Modo ADMIN activado.")
    else:
        st.info("Ingresa el código para ver panel Admin.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧺 Acciones")
st.sidebar.markdown(
    """
    <span class="pill">Registro</span>
    <span class="pill">Login</span>
    <span class="pill">QR</span>
    <span class="pill">Chatbot</span>
    """,
    unsafe_allow_html=True,
)
st.sidebar.caption("Los datos se guardan en Firestore.")

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style="text-align:center;">
        <a href="https://wa.me/523343928767" target="_blank" style="text-decoration:none;">
            <button style="
                background-color:#25D366;
                color:white;
                border:none;
                border-radius:12px;
                padding:12px 16px;
                font-size:14px;
                font-weight:700;
                width:100%;
                cursor:pointer;
            ">
                💬 Contáctanos por WhatsApp
            </button>
        </a>
        <div style="font-size:12px;color:#6A7067;margin-top:6px;">
            Atención y soporte Drop24
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =================================================
# MAIN TABS
# =================================================
tabs = [ "ℹ️ Cómo funciona","📝 Registro", "📲 QR Agendado","🤖 Chatbot Ayuda" ]
if is_admin():
    tabs.append("🛡️ Admin")


tab_objs = st.tabs(tabs)

# =================================================
# TAB 1: REGISTRO
# =================================================
with tab_objs[0]:
    st.markdown(
        """
        <div class="card">
        <b>Registro de usuario Drop24</b><br>
        Este registro también recopila tu domicilio <b>para el servicio a domicilio (próximamente)</b>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("register_form", clear_on_submit=False):
        st.subheader("Datos del usuario")
        c1, c2, c3 = st.columns(3)
        with c1:
            username = st.text_input("Usuario (único) *", placeholder="ej: cliente001").strip().lower()
        with c2:
            full_name = st.text_input("Nombre completo *", placeholder="Nombre y apellido")
        with c3:
            phone = st.text_input("Teléfono (WhatsApp) *", placeholder="55 1234 5678")

        c4, c5 = st.columns(2)
        with c4:
            email = st.text_input("Email *", placeholder="correo@ejemplo.com")
        with c5:
            preferred_contact = st.selectbox("Contacto preferido", ["WhatsApp", "Llamada", "Email"])

        st.subheader("Seguridad de cuenta")
        p1 = st.text_input("Contraseña *", type="password")
        p2 = st.text_input("Confirmar contraseña *", type="password")

        st.markdown("---")
        st.subheader("Domicilio (para servicio a domicilio · próximamente)")

        a1, a2, a3 = st.columns(3)
        with a1:
            street = st.text_input("Calle *")
        with a2:
            ext_number = st.text_input("Número exterior *")
        with a3:
            int_number = st.text_input("Número interior (opcional)")

        b1, b2, b3 = st.columns(3)
        with b1:
            neighborhood = st.text_input("Colonia *")
        with b2:
            borough = st.text_input("Alcaldía / Municipio *")
        with b3:
            postal_code = st.text_input("Código Postal *", max_chars=5)

        c6, c7, c8 = st.columns(3)
        with c6:
            city = st.text_input("Ciudad *", value="CDMX")
        with c7:
            state = st.text_input("Estado *", value="Ciudad de México")
        with c8:
            country = st.text_input("País", value="México")

        d1, d2 = st.columns(2)
        with d1:
            between_streets = st.text_input("Entre calles (opcional)", placeholder="Ej. Acoxpa y…")
        with d2:
            references = st.text_input("Referencias (opcional)", placeholder="Portón negro, edificio…")

        delivery_notes = st.text_area("Instrucciones para entrega (opcional)", placeholder="Horario preferido, si hay caseta, etc.")

        consent = st.checkbox("Acepto que Drop24 guarde mi domicilio para el servicio a domicilio (próximamente) *", value=False)

        submitted = st.form_submit_button("Crear cuenta")

    if submitted:
        payload = {
            "username": username,
            "full_name": (full_name or "").strip(),
            "phone": normalize_phone(phone),
            "email": (email or "").strip().lower(),
            "preferred_contact": preferred_contact,
            "street": (street or "").strip(),
            "ext_number": (ext_number or "").strip(),
            "int_number": (int_number or "").strip(),
            "neighborhood": (neighborhood or "").strip(),
            "borough": (borough or "").strip(),
            "postal_code": (postal_code or "").strip(),
            "city": (city or "").strip(),
            "state": (state or "").strip(),
            "country": (country or "").strip(),
            "between_streets": (between_streets or "").strip(),
            "references": (references or "").strip(),
            "delivery_notes": (delivery_notes or "").strip(),
        }

        required = [
            "username", "full_name", "phone", "email",
            "street", "ext_number", "neighborhood", "borough", "postal_code",
            "city", "state"
        ]
        missing = require_fields(payload, required)

        if missing:
            st.error(f"Faltan campos obligatorios: {', '.join(missing)}")
        elif not payload["postal_code"].isdigit() or len(payload["postal_code"]) != 5:
            st.error("El Código Postal debe ser de 5 dígitos.")
        elif p1 != p2:
            st.error("Las contraseñas no coinciden.")
        elif len(p1) < 6:
            st.error("Contraseña muy corta (mínimo 6).")
        elif not consent:
            st.error("Debes aceptar el guardado de domicilio para continuar.")
        else:
            ref = user_ref(payload["username"])
            if ref.get().exists:
                st.error("Ese usuario ya existe. Elige otro.")
            else:
                ref.set({
                    "username": payload["username"],
                    "password_hash": hash_password(p1),
                    "full_name": payload["full_name"],
                    "phone": payload["phone"],
                    "email": payload["email"],
                    "preferred_contact": payload["preferred_contact"],
                    "address": {
                        "street": payload["street"],
                        "ext_number": payload["ext_number"],
                        "int_number": payload["int_number"],
                        "neighborhood": payload["neighborhood"],
                        "borough": payload["borough"],
                        "postal_code": payload["postal_code"],
                        "city": payload["city"],
                        "state": payload["state"],
                        "country": payload["country"],
                        "between_streets": payload["between_streets"],
                        "references": payload["references"],
                        "delivery_notes": payload["delivery_notes"],
                    },
                    "delivery_service_future": True,
                    "active": True,
                    "role": "USER",
                    "created_at": now_mx_str(),
                    "updated_at": now_mx_str(),
                })
                st.success("Cuenta creada ✅ Ya puedes iniciar sesión en el sidebar.")

# =================================================
# TAB 2: QR AGENDADO
# =================================================
with tab_objs[1]:
    if not st.session_state.auth:
        st.info("Inicia sesión para generar QRs agendados.")
        st.markdown(
            """
            <div class="card">
            <b>¿Qué hace este QR?</b><br>
            El QR contiene un token corto. La app Android validará en Firestore si está activo, dentro de horario y (si aplica) si ya fue usado.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="card">
            <b>Sesión activa:</b> {st.session_state.username}<br>
            <span class="note">Genera un QR con ventana de tiempo. Ideal para distinguir usuarios y reservas.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            client_id = st.text_input("Client ID (opcional)", placeholder="CNA1234...")
        with c2:
            access_type = st.selectbox("Acceso", ["BZ (Buzón)", "L1 (Locker 1)", "L2 (Locker 2)"])
        with c3:
            one_time = st.checkbox("QR de 1 solo uso (recomendado)", value=True)

        st.markdown("### 🔒 Ventana fija (seguridad)")
        st.caption("Los QRs duran **15 minutos** y solo puedes tener **1 QR activo** a la vez.")
        
        prefix = st.text_input("Prefijo QR", value="DROP24", key="qr_prefix_fixed")
        
        # Lockers: apartados solo por 1 hora
        slot_label = None
        locker_day = now_mx().date()
        
        if access_type.startswith("L"):
            st.markdown("#### ⏱️ Apartado de locker (1 hora)")
            locker_day = st.date_input("Día del apartado", value=now_mx().date(), key="locker_day")
            slots = next_full_hour_slots(7, 21)
            slot_map = {slot_to_display(s): s for s in slots}  # display -> value real (24h)
            
            slot_display = st.selectbox(
                "Horario (bloques de 1 hora)",
                list(slot_map.keys()),
                key="locker_slot_display"
            )
            slot_label = slot_map[slot_display]  # esto queda tipo '19:00-20:00'

            st.warning("⚠️ Si no se recoge a tiempo, se guarda en almacén y tendrás que solicitar apoyo vía WhatsApp : +52 33 4392 8767")
        
        if st.button("✅ Crear QR (15 min)", use_container_width=True, key="btn_create_qr_fixed"):
            # 1) Bloqueo: si ya tiene uno activo vigente, no crear otro
            existing = get_active_qr_for_user(st.session_state.username)
            if existing:
                x = existing.to_dict() or {}
                st.error(f"Ya tienes un QR activo vigente hasta: **{x.get('end_time','')}**. Espera a que termine.")
            else:
                token_id = make_token_id()
                payload_qr = f"{prefix}|{token_id}"
        
                # 2) Ventana fija: 15 min (Buzón)
                start_dt = now_mx().replace(second=0, microsecond=0)
                end_dt = start_dt + timedelta(minutes=15)
        
                # 3) Lockers: ventana fija por slot (1 hora)
                if access_type.startswith("L") and slot_label:
                    start_dt, end_dt = slot_to_datetimes(slot_label, locker_day)
        
                token_ref(token_id).set({
                    "token_id": token_id,
                    "payload": payload_qr,
                    "username": st.session_state.username,
                    "client_id": (client_id or "").strip(),
                    "access_type": access_type.split()[0],
        
                    "start_time": dt_to_str(start_dt),
                    "end_time": dt_to_str(end_dt),
        
                    "start_ts": start_dt,
                    "end_ts": end_dt,
        
                    "one_time": bool(one_time),
                    "used": False,
                    "used_at": None,
                    "active": True,
        
                    # info extra locker
                    "locker_day": str(locker_day) if access_type.startswith("L") else None,
                    "locker_slot": slot_label if access_type.startswith("L") else None,
        
                    "created_at": now_mx_str(),
                    "created_by": st.session_state.username,
                })
        
                png = make_qr_png_bytes(payload_qr)
        
                st.success("QR creado y guardado ✅")
                st.code(payload_qr)
                st.image(png, caption="QR generado", width=260)
        
                st.download_button(
                    "⬇️ Descargar QR (PNG)",
                    data=png,
                    file_name=f"DROP24_QR_{token_id}.png",
                    mime="image/png",
                    use_container_width=True,
                )
        
                
                
        st.markdown("---")
        st.markdown("### Mis últimos QRs")

        rows = []
        try:
            docs = (
                db.collection(TOKENS_COL)
                .where("created_by", "==", st.session_state.username)
                .limit(50)   # leo más y ordeno aquí
                .stream()
            )


            for d in docs:
                x = d.to_dict() or {}
                rows.append({
                    "token_id": x.get("token_id"),
                    "access_type": x.get("access_type"),
                    "start_time": x.get("start_time"),
                    "end_time": x.get("end_time"),
                    "one_time": x.get("one_time"),
                    "used": x.get("used"),
                    "active": x.get("active"),
                    "created_at": x.get("created_at"),
                })
        except Exception as e:
            st.error(f"Error leyendo QRs: {e}")

        if rows:
            df_rows = pd.DataFrame(rows)
            if "created_at" in df_rows.columns:
                df_rows = df_rows.sort_values("created_at", ascending=False)
            st.dataframe(df_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no has generado QRs.")

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Aún no has generado QRs.")

# =================================================
# TAB 3: CHATBOT (NUEVO)
# =================================================
with tab_objs[2]:
    st.markdown(
        """
        <div class="card">
        <b>🤖 Chatbot Drop24</b><br>
        Soporte tipo “página de ayuda”: buzón 24/7, QR, lockers, tiempos y cuidado de prendas.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # historial por sesión
    if "drop24_chat" not in st.session_state:
        st.session_state.drop24_chat = [
            {"role": "assistant", "content": "¡Hola! Soy el asistente de Drop24 🧺 ¿Qué duda tienes hoy?"}
        ]
    
    # FAQ rápida
    with st.expander("📌 Preguntas frecuentes (FAQ)", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("¿Cómo funciona el buzón 24/7?", use_container_width=True):
            send_to_drop24_bot("¿Cómo funciona el buzón 24/7?")
        if c2.button("¿Cuánto tarda la entrega?", use_container_width=True):
            send_to_drop24_bot("¿Cuánto tarda la entrega?")
        if c3.button("Problemas con mi QR", use_container_width=True):
            send_to_drop24_bot("Mi QR no funciona, ¿qué reviso?")
        if c4.button("Ver precios", use_container_width=True):
            send_to_drop24_bot("Precios")
    
    st.markdown("---")
    
    # pintar chat
    for m in st.session_state.drop24_chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    
    # input nativo
    user_text = st.chat_input("Escribe tu duda…")
    if user_text:
        send_to_drop24_bot(user_text)


    # botón limpiar
    colA, colB = st.columns([1, 3])
    with colA:
        if st.button("🧹 Limpiar chat", use_container_width=True):
            st.session_state.drop24_chat = [
                {"role": "assistant", "content": "Listo ✅ ¿Qué duda tienes ahora?"}
            ]
            st.rerun()
    with colB:
        st.caption("Tip: usa las FAQ para respuestas rápidas.")

# =================================================
# TAB 4: CÓMO FUNCIONA
# =================================================
with tab_objs[3]:
    st.markdown(
        """
        <div class="card">
        <b>ℹ️ ¿Cómo funciona Drop24?</b><br>
        Aquí te explicamos paso a paso cómo usar el portal, el QR agendado y el buzón/lockers.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="card">
        <b>1) 📝 Registro</b><br>
        - Crea tu usuario y contraseña.<br>
        - Captura tu teléfono y correo.<br>
        - Agrega tu domicilio (para servicio a domicilio próximamente).<br>
        </div>

        <div class="card">
        <b>2) 📲 Login</b><br>
        - Inicia sesión desde la parte superior (más cómodo en teléfono).<br>
        - Con sesión activa podrás generar QRs agendados y ver tus tokens.<br>
        </div>

        <div class="card">
        <b>3) 🔒 QR Agendado (seguridad)</b><br>
        - Puedes generar un QR con ventana de tiempo.<br>
        - Por seguridad: el QR dura <b>15 minutos</b> (buzón) y solo puedes tener <b>1 QR activo</b> a la vez.<br>
        - Si es de 1 uso, se marca como usado después de abrir.<br>
        </div>

        <div class="card">
        <b>4) 🧺 Buzón 24/7</b><br>
        - Te registras y obtienes tu QR.<br>
        - Escaneas el QR en el buzón y depositas tu ropa identificada.<br>
        - Recolectamos en el siguiente horario hábil y comenzamos el proceso.<br>
        </div>

        <div class="card">
        <b>5) 🔐 Lockers (L1 / L2)</b><br>
        - Si eliges Locker, seleccionas un rango de 1 hora (ej. 19:00–20:00).<br>
        - Tu QR solo funciona dentro de esa ventana.<br>
        - Si no se recoge a tiempo, se guarda en almacén y se solicita apoyo por WhatsApp.<br>
        </div>

        <div class="card">
        <b>6) 🤖 Chatbot</b><br>
        - Resuelve dudas rápidas: precios, buzón, QR, tiempos de entrega y especiales.<br>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="card">
        <b>💬 Soporte</b><br>
        ¿Necesitas ayuda con tu QR o locker? Contáctanos por WhatsApp.<br><br>
        👉 <a href="https://wa.me/523343928767" target="_blank"><b>Escríbenos aquí</b></a>
        </div>
        """,
        unsafe_allow_html=True,
    )



# =================================================
# TAB 4: ADMIN
# =================================================
if is_admin():
    with tab_objs[4]:
        st.subheader("🛡️ Admin · Usuarios")
        st.caption("Control básico: ver usuarios y activar/desactivar.")

        docs = db.collection(USERS_COL).limit(200).stream()
        data = []
        for d in docs:
            x = d.to_dict() or {}
            addr = x.get("address", {}) or {}
            data.append({
                "username": x.get("username"),
                "full_name": x.get("full_name"),
                "phone": x.get("phone"),
                "email": x.get("email"),
                "active": x.get("active", True),
                "street": addr.get("street", ""),
                "ext": addr.get("ext_number", ""),
                "colonia": addr.get("neighborhood", ""),
                "borough": addr.get("borough", ""),
                "cp": addr.get("postal_code", ""),
                "created_at": x.get("created_at", ""),
            })

        df = pd.DataFrame(data) if data else pd.DataFrame()
        if df.empty:
            st.info("No hay usuarios todavía.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("### Cambiar estatus de usuario")
        u_target = st.text_input("Username a modificar", placeholder="ej: cliente001").strip().lower()
        new_active = st.selectbox("Nuevo estado", [True, False], index=0)

        if st.button("Aplicar cambio", use_container_width=True, key="btn_admin_toggle"):
            if not u_target:
                st.error("Escribe un username.")
            else:
                ref = user_ref(u_target)
                if not ref.get().exists:
                    st.error("No existe ese usuario.")
                else:
                    ref.update({
                        "active": bool(new_active),
                        "updated_at": now_mx_str(),
                    })
                    st.success("Actualizado ✅")

import textwrap

# =================================================
# CONÓCENOS
# =================================================
conocenos_html = f"""<div class="card" style="margin-top:28px;">
  <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
    {logo_html}
    <div>
      <h3 style="margin:0;color:{C_TEAL_DARK};font-weight:900;">Conócenos</h3>
      <div class="note">Tecnología, confianza y comodidad para tu ropa</div>
    </div>
  </div>

  <hr style="margin:14px 0;border:none;border-top:1px solid #E5EFF3;">

  <p style="font-size:14px;line-height:1.6;margin:0 0 12px 0;">
    <b>Drop24</b> es una plataforma de lavandería moderna que combina
    <b>tecnología</b>, <b>automatización</b> y <b>atención responsable</b>.
    Estamos preparando nuestro <b>servicio a domicilio</b> para que puedas
    olvidarte por completo del lavado de ropa.
  </p>

  <div>
    <span class="pill">Servicio a domicilio · Próximamente</span>
    <span class="pill">Accesos con QR</span>
    <span class="pill">Tecnología Drop24</span>
  </div>
</div>"""

st.markdown(conocenos_html, unsafe_allow_html=True)

# =================================================
# FOOTER (logo abajo)
# =================================================
st.markdown(
    f"""
    <br>
    <div style="text-align:center;margin-top:30px;">
        <div style="display:flex;justify-content:center;margin-bottom:10px;">
            {logo_html}
        </div>
        <div class="note">
            © {now_mx().year} · {ORG_NAME}<br>
            <span class="note">Portal Drop24 en Streamlit + Firestore. Domicilio requerido para servicio a domicilio (próximamente).</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
