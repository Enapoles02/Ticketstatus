import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import uuid
from datetime import datetime, time as dtime
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
    """,
    unsafe_allow_html=True,
)
st.sidebar.caption("Los datos se guardan en Firestore.")

# =================================================
# MAIN TABS
# =================================================
tabs = ["📝 Registro", "📲 QR Agendado"]
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

        st.markdown("### Ventana de tiempo (CDMX)")
        d1, t1, d2, t2 = st.columns([1, 1, 1, 1])
        with d1:
            start_date = st.date_input("Inicio (fecha)", value=now_mx().date(), key="sd")
        with t1:
            start_time = st.time_input("Inicio (hora)", value=now_mx().time().replace(second=0, microsecond=0), key="st")
        with d2:
            end_date = st.date_input("Fin (fecha)", value=now_mx().date(), key="ed")
        with t2:
            end_time = st.time_input("Fin (hora)", value=now_mx().time().replace(second=0, microsecond=0), key="et")

        prefix = st.text_input("Prefijo QR", value="DROP24")

        if st.button("✅ Crear QR", use_container_width=True, key="btn_create_qr"):
            start_dt = datetime.combine(start_date, start_time).replace(tzinfo=MEXICO_TZ)
            end_dt = datetime.combine(end_date, end_time).replace(tzinfo=MEXICO_TZ)

            if end_dt <= start_dt:
                st.error("La hora fin debe ser mayor que la hora inicio.")
            else:
                token_id = make_token_id()
                payload_qr = f"{prefix}|{token_id}"

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
                .limit(25)
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
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Aún no has generado QRs.")


# =================================================
# TAB 3: ADMIN
# =================================================
if is_admin():
    with tab_objs[2]:
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
st.markdown(
    textwrap.dedent(f"""
    <div class="card" style="margin-top:28px;">
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
    </div>
    """),
    unsafe_allow_html=True,
)

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
