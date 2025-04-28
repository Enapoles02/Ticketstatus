# app.py
# -----------------------------------------------------------
# Streamlit dashboard – Aging por Tower
# Autor: ChatGPT – 2025-04-28
# -----------------------------------------------------------
import streamlit as st
import pandas as pd
import datetime as dt
from pathlib import Path

st.set_page_config(
    page_title="Aging Dashboard",
    page_icon="📈",
    layout="wide",
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
DEFAULT_DATAFILE = "tickets.xlsx"          # archivo “por defecto” en el mismo folder
ADMIN_CODE       = "ADMIN"                 # clave mágica para activar modo admin
OPEN_STATES_STOP = ["closed", "resolved", "cancel"]


def load_data(path: Path) -> pd.DataFrame:
    """Lee el Excel y normaliza columnas clave."""
    df = pd.read_excel(path)
    # ─── Limpieza / columnas derivadas ───────────────────────────
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    df["Country"] = df["Client Codes Coding"].str[:2]
    df["CompanyCode"] = df["Client Codes Coding"].str[-4:]
    today = dt.date.today()
    df["Age"] = (today - df["Created"].dt.date).dt.days

    # banderas de aging
    df["TODAY"]      = (df["Age"] == 0)
    df["YESTERDAY"]  = (df["Age"] == 1)
    df["THREE_DAYS"] = (df["Age"].between(2, 3))

    # abierto / cerrado
    pattern = "|".join(OPEN_STATES_STOP)
    df["is_open"] = ~df["State"].str.contains(pattern, case=False, na=False)

    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Genera la tabla de salida requerida."""
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


# ------------------------------------------------------------------
# Estado de la sesión
# ------------------------------------------------------------------
if "admin" not in st.session_state:
    st.session_state.admin = False
if "last_update" not in st.session_state:
    st.session_state.last_update = None
if "data" not in st.session_state:
    default_path = Path(DEFAULT_DATAFILE)
    if default_path.exists():
        st.session_state.data = load_data(default_path)
        st.session_state.last_update = dt.datetime.now()
    else:
        st.session_state.data = None

# ------------------------------------------------------------------
# Barra lateral – Filtros
# ------------------------------------------------------------------
st.sidebar.header("Filtros")
if st.session_state.data is not None:
    df_base = st.session_state.data
    # País
    countries = sorted(df_base["Country"].dropna().unique())
    sel_country = st.sidebar.multiselect("País (CA / US)", countries, default=countries)

    # Compañía (últimos 4 dígitos)
    companies = sorted(df_base["CompanyCode"].dropna().unique())
    sel_company = st.sidebar.multiselect("Compañía (cód. 4 dígitos)", companies, default=companies)

    df_filtered = df_base[
        df_base["Country"].isin(sel_country) &
        df_base["CompanyCode"].isin(sel_company)
    ]
else:
    df_filtered = pd.DataFrame()

# ------------------------------------------------------------------
# Cabecera
# ------------------------------------------------------------------
st.title("📊 Aging Dashboard por Tower")

# Botón para activar modo Admin
with st.expander("🔐 Acceso de administrador"):
    if not st.session_state.admin:
        pwd = st.text_input("Introduce código ADMIN para habilitar la carga de datos", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Modo admin habilitado ✅")
    else:
        st.info("Modo admin activo")
        uploaded = st.file_uploader("Cargar nuevo archivo Excel", type=["xls", "xlsx"])
        if uploaded:
            st.session_state.data = load_data(uploaded)
            st.session_state.last_update = dt.datetime.now()
            st.success("Base de datos actualizada correctamente")

# ------------------------------------------------------------------
# Contenido principal
# ------------------------------------------------------------------
if df_filtered.empty:
    st.warning("No hay datos disponibles. Carga un archivo válido o ajusta los filtros.")
else:
    st.subheader("Resumen por Tower")
    summary_table = summarize(df_filtered)
    st.dataframe(summary_table, use_container_width=True, hide_index=True)

    # Índices rápidos
    total_open   = summary_table["OPEN TICKETS"].sum()
    total_tickets = summary_table["TICKETS (total)"].sum()

    col1, col2 = st.columns(2)
    col1.metric("🎫 Tickets Abiertos", total_open)
    col2.metric("📄 Tickets Totales", total_tickets)

# ------------------------------------------------------------------
# Footer – Hora de la última carga
# ------------------------------------------------------------------
st.markdown(
    f"""
    <div style="position:fixed; bottom:0; left:0; padding:6px 12px; font-size:0.8rem; color:#666;">
        Última actualización:&nbsp;
        <strong>{st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S') if st.session_state.last_update else '–'}</strong>
    </div>
    """,
    unsafe_allow_html=True,
)
