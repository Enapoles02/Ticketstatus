import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore, storage
import uuid
from datetime import datetime, date
import pytz
import io

# =========================
# NEW: Chatbot imports
# =========================
import re
import random
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET

# =================================================
# BRANDING / CONFIG
# =================================================
LOGO_URL = "https://static.wixstatic.com/media/96a5ca_8d5296b476da4799975aa6e250a5dee2~mv2.png/v1/crop/x_53,y_56,w_414,h_328/fill/w_152,h_141,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/SNTCC-aste2.png"

ORG_NAME = (
    "SINDICATO NACIONAL DE TRABAJADORES DE CENTROS DE CONSUMO Y DE SERVICIOS EN GENERAL, "
    "SIMILARES Y CONEXOS DE LA REPUBLICA MEXICANA"
)
ORG_SUB = "AFILIADO A LA FEDERACION NACIONAL DE SINDICATOS PROSOLIDARIDAD"

# Paleta estilo sitio
C_TEAL_DARK = "#055671"
C_TEAL_MID = "#6699A5"
C_CYAN_LIGHT = "#B4DFE8"
C_BG = "#F9FAF8"
C_TEXT_MUTED = "#6A7067"

# =================================================
# STREAMLIT CONFIG
# =================================================
st.set_page_config(
    page_title="SNTCC · Beneficio de Crédito",
    page_icon="💳",
    layout="wide",
)

# =================================================
# CSS (FONDO BLANCO)
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
        border-radius: 8px;
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
# FIREBASE (NO SE TOCA LA CONEXIÓN)
# =================================================
@st.cache_resource
def init_firebase():
    firebase_creds = st.secrets["firebase_credentials"]
    if hasattr(firebase_creds, "to_dict"):
        firebase_creds = firebase_creds.to_dict()

    bucket_name = st.secrets["firebase_bucket"]["firebase_bucket"]

    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_creds)
        firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})

    return firestore.client(), storage.bucket()

db, bucket = init_firebase()
TZ = pytz.timezone("America/Mexico_City")

def now_mx():
    return datetime.now(TZ)

# =================================================
# COLECCIONES
# =================================================
EMPLOYEES_COL = "credit_employees"
LOANS_COL = "credit_loan_requests"
AUDIT_COL = "credit_audit"

# =================================================
# REGLAS DEL PDF
# =================================================
ANNUAL_INTEREST_SIMPLE = 0.12
ADELANTO_MAX_NET_PCT = 0.30
ADELANTO_FEE = 40.0

# demo: estimación neto si no tienes neto real
DEFAULT_NET_FACTOR = 0.80  # neto ~= 80% bruto (placeholder)

# =================================================
# HELPERS
# =================================================
def money(x: float) -> str:
    try:
        return f"${x:,.2f}"
    except:
        return f"${x}"

def months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))

def amort_payment(principal: float, annual_rate: float, months: int) -> float:
    if months <= 0:
        return principal
    r = annual_rate / 12.0
    if r == 0:
        return principal / months
    return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)

def audit_log(action: str, payload: dict):
    try:
        db.collection(AUDIT_COL).document(str(uuid.uuid4())).set({
            "action": action,
            "payload": payload,
            "created_at": now_mx().isoformat(),
            "created_at_ts": now_mx(),
        })
    except:
        pass

# =================================================
# NEW: CHATBOT (ligero + FAQs + chistes + noticias RSS)
# =================================================
BOT_NAME = "SNTCC-Bot"

FAQ_ANSWERS = {
    "como funciona": (
        "📌 Esta página sirve para solicitar:\n"
        "1) *Adelanto de nómina* (semanal o quincenal)\n"
        "2) *Crédito simple* (mensual)\n\n"
        "En el menú de la izquierda ingresas tu *código de empleado* y luego eliges el tipo de crédito en la pestaña *Solicitar*."
    ),
    "adelanto": (
        "💸 *Adelanto de Nómina*\n"
        "• Sin intereses\n"
        "• Hasta 30% del sueldo neto (en demo se estima)\n"
        "• Comisión fija de $40\n"
        "• Frecuencia: semanal o quincenal\n\n"
        "Lo puedes pedir desde la pestaña *Solicitar*."
    ),
    "credito simple": (
        "💳 *Crédito Simple*\n"
        "• Hasta 1 mes de sueldo bruto\n"
        "• Interés anual 12%\n"
        "• Requiere mínimo 6 meses de antigüedad\n"
        "• Descuento mensual vía nómina\n\n"
        "La simulación de pago aparece antes de enviar la solicitud."
    ),
    "admin": (
        "🛡️ *Panel Admin*\n"
        "• Se activa con password (en secrets)\n"
        "• Permite filtrar solicitudes, exportar CSV y cambiar status (APPROVED / REJECTED / PAID)\n\n"
        "Si no ves el tab Admin, no estás autenticado como admin."
    ),
    "login": (
        "🔐 *Login*\n"
        "1) Abre el sidebar\n"
        "2) Escribe tu código (ej. N001)\n"
        "3) Clic en *Ingresar*\n\n"
        "Luego podrás ver *Solicitar* y *Mis solicitudes*."
    ),
    "estatus": (
        "📍 *Estatus típicos*\n"
        "• SUBMITTED: enviada\n"
        "• APPROVED: aprobada\n"
        "• REJECTED: rechazada\n"
        "• PAID: pagada\n\n"
        "Admin puede cambiar el estatus desde el panel."
    ),
}

FUNNY_LINES = [
    "🤖 Soy un bot serio… excepto cuando me preguntan por café. Ahí me desconecto.",
    "😄 Si esto fuera un videojuego, *SUBMITTED* sería el tutorial.",
    "🧠 Consejo financiero del bot: no le prestes dinero a tu ‘yo del futuro’. Siempre se tarda en pagar.",
    "📎 Si el préstamo fuera tamal, aquí ya estaríamos en ‘modo guajolota’.",
    "🧾 *Dato inútil pero importante:* la paciencia no se descuenta vía nómina (todavía).",
]

def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text

def fetch_google_news_rss(query: str = "", lang: str = "es-419", country: str = "MX", max_items: int = 6):
    """
    Trae titulares desde Google News RSS (sin API key).
    Si falla (sin internet), devuelve [].
    """
    try:
        base = "https://news.google.com/rss"
        if query:
            from urllib.parse import quote_plus
            url = f"{base}/search?q={quote_plus(query)}&hl={lang}&gl={country}&ceid={country}:{lang}"
        else:
            url = f"{base}?hl={lang}&gl={country}&ceid={country}:{lang}"

        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=6) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        channel = root.find("channel")
        if channel is None:
            return []

        items = channel.findall("item")[:max_items]
        headlines = []
        for it in items:
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            if title:
                headlines.append({"title": title, "link": link, "pubDate": pub})
        return headlines
    except:
        return []

def bot_reply(user_msg: str, emp: dict | None, is_admin_mode: bool) -> str:
    msg = _normalize(user_msg)

    # saludos
    if any(k in msg for k in ["hola", "buenas", "qué tal", "que tal", "hey", "holi"]):
        name = emp["full_name"].split()[0] if emp and emp.get("full_name") else "👋"
        return f"¡Hola, {name}! Soy {BOT_NAME}. Puedo ayudarte con *cómo usar la página*, *reglas del crédito* o traerte *titulares de hoy* (escribe: **noticias**)."

    # chistes
    if any(k in msg for k in ["chiste", "broma", "algo gracioso", "hazme reir", "hazme reír"]):
        return random.choice(FUNNY_LINES)

    # hora
    if "hora" in msg or "qué hora" in msg or "que hora" in msg:
        return f"🕒 Hora CDMX: **{now_mx().strftime('%H:%M')}**"

    # noticias (top)
    if msg.startswith("noticias") or "noticia" in msg or "titulares" in msg:
        q = ""
        parts = msg.split(" ", 1)
        if len(parts) == 2:
            q = parts[1].strip()

        heads = fetch_google_news_rss(query=q, max_items=6)
        if not heads:
            return (
                "🗞️ Ahorita no pude traer noticias (puede ser falta de internet en el hosting). "
                "Pero puedo responder dudas de la página. Prueba: **cómo funciona**, **adelanto**, **crédito simple**, **admin**."
            )

        lines = []
        if q:
            lines.append(f"🗞️ Titulares de hoy sobre: **{q}**")
        else:
            lines.append("🗞️ Titulares de hoy (MX)")

        for i, h in enumerate(heads, 1):
            title = h["title"]
            link = h["link"]
            lines.append(f"{i}. [{title}]({link})")

        lines.append("\n*Fuente: Google News RSS (titulares).*\n")
        return "\n".join(lines)

    # FAQs por keywords
    if "como funciona" in msg or "cómo funciona" in msg or "funcion" in msg:
        return FAQ_ANSWERS["como funciona"]

    if "adelanto" in msg:
        return FAQ_ANSWERS["adelanto"]

    if "credito simple" in msg or "crédito simple" in msg or ("credito" in msg and "simple" in msg):
        return FAQ_ANSWERS["credito simple"]

    if "admin" in msg or "administrador" in msg:
        return FAQ_ANSWERS["admin"]

    if "login" in msg or "iniciar" in msg or "codigo" in msg or "código" in msg:
        return FAQ_ANSWERS["login"]

    if "estatus" in msg or "status" in msg:
        return FAQ_ANSWERS["estatus"]

    # contexto del usuario
    if emp and ("mi sueldo" in msg or "mi salario" in msg):
        gross = float(emp.get("gross_monthly_salary", 0.0))
        return f"Tu sueldo bruto mensual en el sistema está registrado como **{money(gross)}** (demo)."

    # fallback simpático
    extras = [
        "Si quieres, escribe **noticias** para titulares de hoy.",
        "Puedo explicarte: **adelanto**, **crédito simple**, **admin** o **cómo funciona**.",
        "Si quieres algo gracioso, escribe **chiste** 😄",
    ]
    return "🤖 No estoy 100% seguro de eso, pero puedo ayudarte si me dices qué necesitas.\n\n" + random.choice(extras)

# =================================================
# EMPLEADOS: SEED 3 FICTICIOS (IDEMPOTENTE)
# =================================================
def seed_employees_if_needed():
    existing = list(db.collection(EMPLOYEES_COL).limit(1).stream())
    if existing:
        return

    employees = [
        {
            "employee_code": "N001",
            "full_name": "Sergio Napoles",
            "gross_monthly_salary": 80000.0,
            "hire_date": date(2024, 4, 1).isoformat(),  # > 6 meses
            "active": True,
        },
        {
            "employee_code": "R002",
            "full_name": "Carla Rojas",
            "gross_monthly_salary": 42000.0,
            "hire_date": date(2025, 10, 15).isoformat(),  # < 6 meses (para probar regla)
            "active": True,
        },
        {
            "employee_code": "G003",
            "full_name": "Luis Garcia",
            "gross_monthly_salary": 55000.0,
            "hire_date": date(2025, 1, 10).isoformat(),  # > 6 meses
            "active": True,
        },
    ]

    batch = db.batch()
    for e in employees:
        doc_id = str(uuid.uuid4())
        ref = db.collection(EMPLOYEES_COL).document(doc_id)
        batch.set(ref, {
            **e,
            "created_at": now_mx().isoformat(),
            "created_at_ts": now_mx(),
        })
    batch.commit()
    audit_log("seed_employees", {"count": len(employees)})

seed_employees_if_needed()

def get_employee_by_code(code: str):
    code = (code or "").strip().upper()
    if not code:
        return None

    docs = db.collection(EMPLOYEES_COL).where("employee_code", "==", code).limit(1).stream()
    for d in docs:
        data = d.to_dict()
        data["_id"] = d.id
        return data
    return None

# =================================================
# LOANS
# =================================================
def submit_loan_request(employee: dict, loan_type: str, requested_amount: float, frequency: str,
                       term_months: int | None, notes: str, computed: dict):
    payload = {
        "employee_code": employee["employee_code"],
        "employee_name": employee["full_name"],
        "loan_type": loan_type,  # ADELANTO_NOMINA | CREDITO_SIMPLE
        "requested_amount": float(requested_amount),
        "frequency": frequency,  # SEMANAL | QUINCENAL | MENSUAL
        "term_months": int(term_months) if term_months else None,
        "notes": (notes or "").strip(),
        "status": "SUBMITTED",
        "created_at": now_mx().isoformat(),
        "created_at_ts": now_mx(),
        "updated_at": now_mx().isoformat(),
        "updated_at_ts": now_mx(),
        **computed,
    }

    doc_id = str(uuid.uuid4())
    db.collection(LOANS_COL).document(doc_id).set(payload)
    audit_log("loan_submitted", {"loan_id": doc_id, **payload})
    return doc_id

def fetch_loans_for_employee(employee_code: str, limit=200):
    employee_code = (employee_code or "").strip().upper()
    if not employee_code:
        return pd.DataFrame()

    rows = []

    # 1) Query SIN order_by (evita índice compuesto)
    try:
        docs = (
            db.collection(LOANS_COL)
            .where("employee_code", "==", employee_code)
            .limit(limit)
            .stream()
        )
        for d in docs:
            x = d.to_dict()
            x["_id"] = d.id
            rows.append(x)

    except Exception as e:
        # 2) Fallback: traer todo y filtrar local (último recurso, pero no rompe la app)
        try:
            docs = db.collection(LOANS_COL).stream()
            for d in docs:
                x = d.to_dict()
                if str(x.get("employee_code", "")).strip().upper() == employee_code:
                    x["_id"] = d.id
                    rows.append(x)
        except Exception as e2:
            st.error(f"Error consultando solicitudes en Firestore: {e2}")
            return pd.DataFrame()

    df = pd.DataFrame(rows) if rows else pd.DataFrame()

    # Orden local (equivalente a order_by desc)
    if not df.empty:
        if "created_at" in df.columns:
            df = df.sort_values("created_at", ascending=False)
        elif "created_at_ts" in df.columns:
            df = df.sort_values("created_at_ts", ascending=False)

    return df

def fetch_all_loans(limit=500):
    try:
        docs = (
            db.collection(LOANS_COL)
            .order_by("created_at_ts", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
    except:
        docs = db.collection(LOANS_COL).stream()

    rows = []
    for d in docs:
        x = d.to_dict()
        x["_id"] = d.id
        rows.append(x)
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def update_loan_status(loan_id: str, new_status: str, admin_comment: str = ""):
    new_status = (new_status or "").strip().upper()
    db.collection(LOANS_COL).document(loan_id).update({
        "status": new_status,
        "admin_comment": (admin_comment or "").strip(),
        "updated_at": now_mx().isoformat(),
        "updated_at_ts": now_mx(),
    })
    audit_log("loan_status_updated", {"loan_id": loan_id, "status": new_status, "comment": admin_comment})

# =================================================
# ADMIN AUTH (secrets)
# =================================================
def is_admin():
    try:
        pw = st.secrets["credit_admin"]["password"]
    except:
        return False
    entered = st.session_state.get("admin_password_value", "")
    return entered == pw

# =================================================
# HEADER
# =================================================
st.markdown(
    f"""
    <div class="corp-header">
        <div class="corp-header-left">
            <img class="corp-logo" src="{LOGO_URL}" />
            <div>
                <div class="corp-header-title">{ORG_NAME}</div>
                <div class="corp-header-sub">{ORG_SUB}</div>
            </div>
        </div>
        <div class="corp-header-right">
            <div><b>Plan de Beneficio de Crédito</b></div>
            <div style="opacity:0.92;">Portal de solicitudes</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div class='big-title'>Beneficio de Crédito</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Adelanto de nómina · Crédito simple · Panel Admin</div>", unsafe_allow_html=True)

# =================================================
# SIDEBAR (LOGIN + ADMIN)
# =================================================
st.sidebar.title("🔐 Accesos")

with st.sidebar.expander("👤 Login Empleado", expanded=True):
    code_input = st.text_input("Código de empleado (ej. N001)", value=st.session_state.get("employee_code", ""))
    if st.button("Ingresar", use_container_width=True):
        emp = get_employee_by_code(code_input)
        if not emp or not emp.get("active", True):
            st.error("Código inválido o empleado inactivo.")
        else:
            st.session_state.employee_code = emp["employee_code"]
            st.session_state.employee = emp
            st.success(f"Bienvenido(a), {emp['full_name']} ({emp['employee_code']})")

    if st.session_state.get("employee"):
        emp = st.session_state["employee"]
        st.caption(f"Sesión: **{emp['full_name']}** · {emp['employee_code']}")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.pop("employee", None)
            st.session_state.pop("employee_code", None)
            st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("🛡️ Admin", expanded=False):
    st.text_input("Password admin", type="password", key="admin_password_value")
    if is_admin():
        st.success("Modo ADMIN activado.")
    else:
        st.info("Ingresa password para ver panel Admin.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧪 Códigos demo")
st.sidebar.markdown(
    """
    <span class="pill">N001</span>
    <span class="pill">R002</span>
    <span class="pill">G003</span>
    """,
    unsafe_allow_html=True,
)
st.sidebar.caption("Los empleados demo se guardan en Firebase (colección credit_employees).")

# =================================================
# MAIN
# =================================================
emp = st.session_state.get("employee")

if not emp:
    st.info("Inicia sesión con tu **código de empleado** para solicitar un crédito.")
    st.markdown(
        """
        <div class="card">
        <b>Reglas del Plan (según PDF):</b><br><br>
        ✅ <b>Adelanto de Nómina</b>: semanal o quincenal, hasta 30% del sueldo neto, sin intereses, comisión $40 por transacción.<br>
        ✅ <b>Crédito Simple</b>: hasta 1 mes de sueldo bruto, interés anual 12%, requiere al menos 6 meses de antigüedad.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =================================================
    # NEW: CHATBOT UI (Disponible aun sin login)
    # =================================================
    st.markdown("---")
    st.markdown("## 💬 Chatbot")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": f"Hola 👋 Soy {BOT_NAME}. Pregúntame por **cómo funciona**, **adelanto**, **crédito simple**, **admin**, o escribe **noticias** / **chiste**."}
        ]

    # Botones rápidos
    cA, cB, cC = st.columns(3)
    with cA:
        if st.button("😄 Chiste", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": "chiste"})
            st.rerun()
    with cB:
        if st.button("🧾 Cómo funciona", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": "cómo funciona"})
            st.rerun()
    with cC:
        if st.button("🗞️ Noticias", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": "noticias"})
            st.rerun()

    # Render historial
    for m in st.session_state.chat_history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_prompt = st.chat_input("Escribe tu pregunta… (ej: 'cómo funciona', 'noticias economia', 'chiste')")
    if user_prompt:
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        reply = bot_reply(user_prompt, st.session_state.get("employee"), is_admin())
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

        audit_log("chat_message", {
            "employee_code": "",
            "is_admin": bool(is_admin()),
            "user_msg": user_prompt,
            "bot_reply": reply[:900],
        })

    st.stop()

# Datos del empleado
gross = float(emp.get("gross_monthly_salary", 0.0))
hire_date_str = emp.get("hire_date", "2025-01-01")
try:
    hire_dt = date.fromisoformat(hire_date_str)
except:
    hire_dt = date(2025, 1, 1)

antig_months = months_between(hire_dt, now_mx().date())
estimated_net = gross * DEFAULT_NET_FACTOR
max_adelanto = estimated_net * ADELANTO_MAX_NET_PCT
max_credito_simple = gross

# Tabs
tabs = ["📝 Solicitar", "📄 Mis solicitudes", "💬 Chatbot"]
if is_admin():
    tabs.append("🛡️ Admin")

tab_objs = st.tabs(tabs)

# =================================================
# TAB: SOLICITAR
# =================================================
with tab_objs[0]:
    st.markdown(
        f"""
        <div class="card">
        <b>Empleado:</b> {emp["full_name"]} · <b>Código:</b> {emp["employee_code"]}<br>
        <b>Sueldo bruto mensual:</b> {money(gross)}<br>
        <b>Antigüedad:</b> {antig_months} meses (ingreso: {hire_date_str})<br>
        <span class="note">* Para demo, el sueldo neto se estima al {int(DEFAULT_NET_FACTOR*100)}% del bruto: {money(estimated_net)}.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    loan_type = st.radio(
        "¿Qué tipo de crédito deseas solicitar?",
        ["Adelanto de nómina", "Crédito simple"],
        horizontal=True
    )

    st.markdown("---")

    if loan_type == "Adelanto de nómina":
        st.subheader("Adelanto de Nómina")
        st.caption("Liquidez inmediata: hasta 30% del sueldo neto, sin intereses, comisión $40 por transacción.")

        c1, c2 = st.columns(2)
        with c1:
            frequency = st.selectbox("Frecuencia", ["SEMANAL", "QUINCENAL"])
        with c2:
            requested = st.number_input(
                "Monto a solicitar",
                min_value=0.0,
                max_value=float(max_adelanto),
                value=float(max_adelanto),
                step=100.0,
            )

        st.info(f"Máximo permitido (30% neto estimado): **{money(max_adelanto)}** · Comisión: **{money(ADELANTO_FEE)}**")

        notes = st.text_area("Notas (opcional)", placeholder="Ej. imprevisto médico, pago urgente, etc.")

        # Validación / resumen
        total_to_discount = float(requested) + ADELANTO_FEE
        st.markdown(
            f"""
            <div class="card">
            <b>Resumen</b><br>
            Monto solicitado: <b>{money(requested)}</b><br>
            Comisión: <b>{money(ADELANTO_FEE)}</b><br>
            Total a descontar vía nómina: <b>{money(total_to_discount)}</b><br>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("✅ Enviar solicitud de Adelanto", use_container_width=True):
            if requested <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                computed = {
                    "rule_max_adelanto": float(max_adelanto),
                    "estimated_net_salary": float(estimated_net),
                    "fee": float(ADELANTO_FEE),
                    "total_discount": float(total_to_discount),
                    "interest_annual": 0.0,
                    "eligibility_ok": True,
                    "eligibility_reason": "",
                }
                loan_id = submit_loan_request(
                    emp,
                    "ADELANTO_NOMINA",
                    float(requested),
                    frequency,
                    None,
                    notes,
                    computed
                )
                st.success(f"Solicitud enviada ✅ (ID: {loan_id})")

    else:
        st.subheader("Crédito Simple")
        st.caption("Financiamiento: hasta 1 mes de sueldo bruto, interés anual 12%, pagos periódicos vía nómina.")

        eligible = antig_months >= 6
        if not eligible:
            st.warning("⚠️ No cumples el requisito: se requiere **mínimo 6 meses de antigüedad**.")

        c1, c2, c3 = st.columns(3)
        with c1:
            requested = st.number_input(
                "Monto a solicitar",
                min_value=0.0,
                max_value=float(max_credito_simple),
                value=float(max_credito_simple),
                step=500.0,
            )
        with c2:
            term_months = st.selectbox("Plazo (meses)", [3, 6, 9, 12, 18, 24], index=1)
        with c3:
            frequency = st.selectbox("Frecuencia de descuento", ["MENSUAL"])

        monthly_payment = amort_payment(float(requested), ANNUAL_INTEREST_SIMPLE, int(term_months))
        total_pay = monthly_payment * int(term_months)
        total_interest = total_pay - float(requested)

        st.info(f"Máximo permitido (1 mes bruto): **{money(max_credito_simple)}** · Interés anual: **12%**")

        notes = st.text_area("Notas (opcional)", placeholder="Ej. educación, salud, mejoras del hogar, etc.")

        st.markdown(
            f"""
            <div class="card">
            <b>Simulación (referencial)</b><br>
            Principal: <b>{money(requested)}</b><br>
            Plazo: <b>{term_months} meses</b><br>
            Pago mensual estimado: <b>{money(monthly_payment)}</b><br>
            Total a pagar estimado: <b>{money(total_pay)}</b><br>
            Interés total estimado: <b>{money(total_interest)}</b><br>
            <span class="note">* Cálculo amortizado estándar con 12% anual (referencial).</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("✅ Enviar solicitud de Crédito Simple", use_container_width=True):
            if requested <= 0:
                st.error("El monto debe ser mayor a 0.")
            elif not eligible:
                computed = {
                    "rule_max_credito_simple": float(max_credito_simple),
                    "interest_annual": float(ANNUAL_INTEREST_SIMPLE),
                    "term_months_calc": int(term_months),
                    "monthly_payment_est": float(monthly_payment),
                    "total_pay_est": float(total_pay),
                    "total_interest_est": float(total_interest),
                    "eligibility_ok": False,
                    "eligibility_reason": "Requiere 6 meses de antigüedad",
                    "employee_antig_months": int(antig_months),
                }
                loan_id = submit_loan_request(
                    emp,
                    "CREDITO_SIMPLE",
                    float(requested),
                    "MENSUAL",
                    int(term_months),
                    notes,
                    computed
                )
                st.warning(f"Solicitud registrada, pero marcada como NO elegible por antigüedad (ID: {loan_id}).")
            else:
                computed = {
                    "rule_max_credito_simple": float(max_credito_simple),
                    "interest_annual": float(ANNUAL_INTEREST_SIMPLE),
                    "term_months_calc": int(term_months),
                    "monthly_payment_est": float(monthly_payment),
                    "total_pay_est": float(total_pay),
                    "total_interest_est": float(total_interest),
                    "eligibility_ok": True,
                    "eligibility_reason": "",
                    "employee_antig_months": int(antig_months),
                }
                loan_id = submit_loan_request(
                    emp,
                    "CREDITO_SIMPLE",
                    float(requested),
                    "MENSUAL",
                    int(term_months),
                    notes,
                    computed
                )
                st.success(f"Solicitud enviada ✅ (ID: {loan_id})")

# =================================================
# TAB: MIS SOLICITUDES
# =================================================
with tab_objs[1]:
    st.subheader("📄 Mis solicitudes")
    df_my = fetch_loans_for_employee(emp["employee_code"], limit=200)

    if df_my.empty:
        st.info("Aún no tienes solicitudes registradas.")
    else:
        cols = [
            "created_at", "loan_type", "requested_amount", "frequency", "term_months",
            "status", "eligibility_ok", "eligibility_reason", "admin_comment"
        ]
        show_cols = [c for c in cols if c in df_my.columns]

        df_view = df_my.copy()

        if "requested_amount" in df_view.columns:
            df_view["requested_amount"] = df_view["requested_amount"].apply(lambda x: money(float(x)))

        st.dataframe(df_view[show_cols], use_container_width=True)

        csv_bytes = df_my.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar mis solicitudes (CSV)",
            data=csv_bytes,
            file_name=f"mis_solicitudes_{emp['employee_code']}.csv",
            mime="text/csv",
            use_container_width=True,
        )

# =================================================
# TAB: CHATBOT
# =================================================
with tab_objs[2]:
    st.subheader("💬 Chatbot")
    st.caption("Preguntas frecuentes, ayuda de la página, chistes y titulares del día (RSS).")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": f"Hola 👋 Soy {BOT_NAME}. Pregúntame por **cómo funciona**, **adelanto**, **crédito simple**, **admin**, o escribe **noticias** / **chiste**."}
        ]

    # Botones rápidos
    cA, cB, cC = st.columns(3)
    with cA:
        if st.button("😄 Chiste", use_container_width=True, key="btn_chiste_tab"):
            st.session_state.chat_history.append({"role": "user", "content": "chiste"})
            st.rerun()
    with cB:
        if st.button("🧾 Cómo funciona", use_container_width=True, key="btn_comofunciona_tab"):
            st.session_state.chat_history.append({"role": "user", "content": "cómo funciona"})
            st.rerun()
    with cC:
        if st.button("🗞️ Noticias", use_container_width=True, key="btn_noticias_tab"):
            st.session_state.chat_history.append({"role": "user", "content": "noticias"})
            st.rerun()

    # Render historial
    for m in st.session_state.chat_history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_prompt = st.chat_input("Escribe tu pregunta… (ej: 'cómo funciona', 'noticias economia', 'chiste')", key="chat_input_tab")
    if user_prompt:
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        reply = bot_reply(user_prompt, st.session_state.get("employee"), is_admin())
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

        audit_log("chat_message", {
            "employee_code": (st.session_state.get("employee") or {}).get("employee_code", ""),
            "is_admin": bool(is_admin()),
            "user_msg": user_prompt,
            "bot_reply": reply[:900],
        })

# =================================================
# TAB: ADMIN
# =================================================
if is_admin():
    with tab_objs[3]:
        st.subheader("🛡️ Panel Admin")
        st.caption("Revisión de solicitudes, aprobación/rechazo, control de estatus y exportación.")

        df_all = fetch_all_loans(limit=500)

        if df_all.empty:
            st.info("No hay solicitudes registradas todavía.")
        else:
            # Filtros
            c1, c2, c3 = st.columns(3)
            with c1:
                status_filter = st.selectbox("Filtrar por status", ["(Todos)", "SUBMITTED", "APPROVED", "REJECTED", "PAID"], index=0)
            with c2:
                type_filter = st.selectbox("Filtrar por tipo", ["(Todos)", "ADELANTO_NOMINA", "CREDITO_SIMPLE"], index=0)
            with c3:
                search_code = st.text_input("Buscar por código empleado", value="").strip().upper()

            df_f = df_all.copy()
            if status_filter != "(Todos)" and "status" in df_f.columns:
                df_f = df_f[df_f["status"] == status_filter]
            if type_filter != "(Todos)" and "loan_type" in df_f.columns:
                df_f = df_f[df_f["loan_type"] == type_filter]
            if search_code and "employee_code" in df_f.columns:
                df_f = df_f[df_f["employee_code"].astype(str).str.upper().str.contains(search_code)]

            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total", len(df_f))
            if "status" in df_f.columns:
                k2.metric("SUBMITTED", int((df_f["status"] == "SUBMITTED").sum()))
                k3.metric("APPROVED", int((df_f["status"] == "APPROVED").sum()))
                k4.metric("REJECTED", int((df_f["status"] == "REJECTED").sum()))
            else:
                k2.metric("SUBMITTED", 0)
                k3.metric("APPROVED", 0)
                k4.metric("REJECTED", 0)

            st.markdown("---")

            # Tabla principal
            show_cols = [
                "created_at", "employee_code", "employee_name", "loan_type",
                "requested_amount", "frequency", "term_months", "status",
                "eligibility_ok", "eligibility_reason", "admin_comment", "_id"
            ]
            show_cols = [c for c in show_cols if c in df_f.columns]

            df_view = df_f.copy()
            if "requested_amount" in df_view.columns:
                df_view["requested_amount"] = df_view["requested_amount"].apply(lambda x: money(float(x)))

            st.dataframe(df_view[show_cols], use_container_width=True, height=420)

            # Export CSV
            csv_bytes = df_f.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Exportar (CSV) lo filtrado",
                data=csv_bytes,
                file_name="solicitudes_filtradas.csv",
                mime="text/csv",
                use_container_width=True,
            )

            st.markdown("---")

            # Acciones sobre solicitud
            st.markdown("### ✅ Acciones")
            loan_id = st.text_input("Pega el ID (_id) de la solicitud", value="").strip()
            new_status = st.selectbox("Cambiar status a", ["APPROVED", "REJECTED", "PAID"], index=0)
            admin_comment = st.text_area("Comentario Admin (opcional)", placeholder="Ej. Aprobado; descuento vía nómina a partir de X fecha.")

            if st.button("Aplicar cambio", use_container_width=True):
                if not loan_id:
                    st.error("Pega el ID (_id) de la solicitud.")
                else:
                    try:
                        update_loan_status(loan_id, new_status, admin_comment)
                        st.success("Actualizado ✅")
                    except Exception as e:
                        st.error(f"Error: {e}")

# =================================================
# FOOTER
# =================================================
st.markdown(
    f"""
    <br>
    <div class="note" style="text-align:center;">
        © {now_mx().year} · {ORG_SUB}<br>
        <span class="note">Este portal es una demo en Streamlit + Firebase. Reglas aplicadas según el documento del plan de crédito.</span>
    </div>
    """,
    unsafe_allow_html=True,
)
