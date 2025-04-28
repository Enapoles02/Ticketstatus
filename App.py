# app.py
# -----------------------------------------------------------
# Streamlit dashboard – Aging por Tower + Firebase (secrets)
# -----------------------------------------------------------
import streamlit as st
import pandas as pd
import datetime as dt
import json
import firebase_admin
from firebase_admin import credentials, firestore
from io import BytesIO

st.set_page_config(
    page_title="Aging Dashboard",
    page_icon="📈",
    layout="wide",
)

# -----------------------------------------------------------
# Constantes
# -----------------------------------------------------------
ADMIN_CODE = "ADMIN"
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"

# -----------------------------------------------------------
# Inicializar Firebase desde secrets
# -----------------------------------------------------------
if not firebase_admin._apps:
    firebase_credentials = json.loads(st.secrets["firebase_credentials"])
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# -----------------------------------------------------------
# Funciones
# -----------------------------------------------------------
def load_data_from_excel(uploaded_file) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file)
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    today_midnight = pd.Timestamp("today").normalize()
    df["Age"] = (today_midnight - df["Created"].dt.normalize()).dt.days
    df["Country"] = df["Client Codes Coding"].str[:2]
    df["CompanyCode"] = df["Client Codes Coding"].str[-4:]
    df["TODAY"] = df["Age"] == 0
    df["YESTERDAY"] = df["Age"] == 1
    df["THREE_DAYS"] = df["Age"].between(2, 3)
    pattern = "|".join(["closed", "resolved", "cancel"])
    df["is_open"] = ~df["State"].str.contains(pattern, case=False, na=False)
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("Assignment group").agg(
        OPEN_TICKETS=("is_open", "sum"),
        TICKETS_total=("Number", "count"),
        TODAY=("TODAY", "sum"),
        YESTERDAY=("YESTERDAY", "sum"),
        THREE_DAYS=("THREE_DAYS", "sum"),
    ).reset_index()
    agg = agg.rename(columns={
        "Assignment group": "TOWER",
        "TICKETS_total": "TICKETS (total)",
        "THREE_DAYS": "3 DAYS"
    })
    return agg.sort_values("TOWER")


def upload_to_firestore(df: pd.DataFrame):
    """Sube DataFrame como JSON a Firestore."""
    data_json = json.loads(df.to_json(orient="records"))
    db.collection(COLLECTION_NAME).document(DOCUMENT_ID).set({
        "data": data_json,
        "last_update": dt.datetime.utcnow()
    })


def download_from_firestore() -> (pd.DataFrame, dt.datetime):
    """Descarga DataFrame desde Firestore."""
    doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
    if doc.exists:
        content = doc.to_dict()
        df = pd.DataFrame(content["data"])
        return df, content.get("last_update")
    else:
        return pd.DataFrame(), None

# -----------------------------------------------------------
# Estado de sesión
# -----------------------------------------------------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# -----------------------------------------------------------
# Título
# -----------------------------------------------------------
st.title("📊 Aging Dashboard por Tower (con Firebase)")

# -----------------------------------------------------------
# Acceso Admin para carga
# -----------------------------------------------------------
with st.expander("🔐 Acceso de administrador"):
    if not st.session_state.admin:
        pwd = st.text_input("Introduce código ADMIN para habilitar carga", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Modo admin habilitado ✅")
    else:
        st.info("Modo admin activo")
        uploaded = st.file_uploader("Cargar nuevo archivo Excel", type=["xls", "xlsx"])
        if uploaded:
            df_new = load_data_from_excel(uploaded)
            upload_to_firestore(df_new)
            st.success("Base de datos subida exitosamente 🔥")
            st.rerun()

# -----------------------------------------------------------
# Leer data desde Firebase
# -----------------------------------------------------------
df, last_update = download_from_firestore()

# -----------------------------------------------------------
# Sidebar – Filtros
# -----------------------------------------------------------
if not df.empty:
    st.sidebar.header("Filtros")
    countries = sorted(df["Country"].dropna().unique())
    companies = sorted(df["CompanyCode"].dropna().unique())

    sel_country = st.sidebar.multiselect("País (CA / US)", countries, default=countries)
    sel_company = st.sidebar.multiselect("Compañía (últimos 4 dígitos)", companies, default=companies)

    df_filtered = df[
        df["Country"].isin(sel_country) &
        df["CompanyCode"].isin(sel_company)
    ]
else:
    df_filtered = pd.DataFrame()

# -----------------------------------------------------------
# Dashboard
# -----------------------------------------------------------
if df_filtered.empty:
    st.warning("No hay datos disponibles.")
else:
    st.subheader("Resumen por Tower")
    summary = summarize(df_filtered)
    st.dataframe(summary, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    col1.metric("🎫 Tickets abiertos", int(summary["OPEN_TICKETS"].sum()))
    col2.metric("📄 Tickets totales", int(summary["TICKETS (total)"].sum()))

# -----------------------------------------------------------
# Footer – Última carga
# -----------------------------------------------------------
st.markdown(
    f"""
    <div style="position:fixed; bottom:0; left:0; padding:6px 12px; font-size:0.8rem; color:#666;">
        Última actualización:&nbsp;
        <strong>{last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else '–'}</strong>
    </div>
    """,
    unsafe_allow_html=True,
)
