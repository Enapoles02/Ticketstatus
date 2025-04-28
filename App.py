# app.py
# ------------------------------------------------------------------
# Streamlit dashboard – Aging por Tower
# ------------------------------------------------------------------
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
# Constantes
# ------------------------------------------------------------------
DEFAULT_DATAFILE = "tickets.xlsx"        # nombre por defecto si existe en la carpeta
ADMIN_CODE       = "ADMIN"               # clave para activar modo admin
OPEN_STATES_STOP = ["closed", "resolved", "cancel"]  # palabras que definen ticket cerrado


# ------------------------------------------------------------------
# Funciones
# ------------------------------------------------------------------
def load_data(path_or_buffer) -> pd.DataFrame:
    """Lee el Excel y construye todas las columnas necesarias."""
    df = pd.read_excel(path_or_buffer)

    # --- Columnas derivadas ---------------------------------------------------
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")

    # Cálculo robusto del age en días
    today_midnight = pd.Timestamp("today").normalize()
    df["Age"] = (today_midnight - df["Created"].dt.normalize()).dt.days

    df["Country"]     = df["Client Codes Coding"].str[:2]
    df["CompanyCode"] = df["Client Codes Coding"].str[-4:]

    # Banderas de aging
    df["TODAY"]      = df["Age"] == 0
    df["YESTERDAY"]  = df["Age"] == 1
    df["THREE_DAYS"] = df["Age"].between(2, 3)

    # Abierto / cerrado
    pattern = "|".join(OPEN_STATES_STOP)
    df["is_open"] = ~df["State"].str.contains(pattern, case=False, na=False)

    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve tabla con métricas por 'Assignment group'."""
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
# Estado de sesión
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
    base_df = st.session_state.data

    # Filtro País
    countries = sorted(base_df["Country"].dropna().unique())
    sel_country = st.sidebar.multiselect("País (CA / US)", countries, default=countries)

    # Filtro CompanyCode
    companies = sorted(base_df["CompanyCode"].dropna().unique())
    sel_company = st.sidebar.multiselect("Compañía (últimos 4 dígitos)", companies, default=companies)

    df_filtered = base_df[
        base_df["Country"].isin(sel_country) &
        base_df["CompanyCode"].isin(sel_company)
    ]
else:
    df_filtered = pd.DataFrame()

# ------------------------------------------------------------------
# Cabecera de la página
# ------------------------------------------------------------------
st.title("📊 Aging Dashboard por Tower")

# ------------------------------------------------------------------
# Expander para modo Admin y carga de archivo
# ------------------------------------------------------------------
with st.expander("🔐 Acceso de administrador"):
    if not st.session_state.admin:
        pwd = st.text_input("Introduce código ADMIN para habilitar la carga de datos", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Modo admin habilitado ✅")
    else:
        st.info("Modo admin activo")
        uploaded = st.file_uploader("Cargar nuevo archivo Excel", type=["xls", "xlsx"])
        if uploaded is not None:
            st.session_state.data = load_data(uploaded)
            st.session_state.last_update = dt.datetime.now()
            st.success("Base de datos actualizada correctamente")
            st.experimental_rerun()

# ------------------------------------------------------------------
# Dashboard principal
# ------------------------------------------------------------------
if df_filtered.empty:
    st.warning("No hay datos disponibles. Carga un archivo válido o ajusta los filtros.")
else:
    st.subheader("Resumen por Tower")
    summary = summarize(df_filtered)
    st.dataframe(summary, use_container_width=True, hide_index=True)

    # Métricas globales
    col1, col2 = st.columns(2)
    col1.metric("🎫 Tickets abiertos", int(summary["OPEN_TICKETS"].sum()))
    col2.metric("📄 Tickets totales", int(summary["TICKETS (total)"].sum()))

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
