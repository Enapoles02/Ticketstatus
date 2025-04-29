import streamlit as st
import pandas as pd
import datetime as dt
import json
import firebase_admin
from firebase_admin import credentials, firestore
import io
import matplotlib.pyplot as plt

st.set_page_config(page_title="Tickets Dashboard", page_icon="📈", layout="wide")

ADMIN_CODE = "ADMIN"
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"
ALLOWED_TOWERS = ["MDM", "P2P", "O2C", "R2R"]

# Firebase initialization
if not firebase_admin._apps:
    firebase_credentials = json.loads(st.secrets["firebase_credentials"])
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

def safe_age(created_date):
    try:
        if pd.isna(created_date):
            return None
        return (pd.Timestamp("today").normalize() - pd.to_datetime(created_date).normalize()).days
    except Exception:
        return None

def load_data_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    
    # Limpieza de encabezados
    df.columns = df.columns.str.strip()

    created_col = [col for col in df.columns if "created" in col.lower()]
    if created_col:
        df["Created"] = pd.to_datetime(df[created_col[0]], errors="coerce")
    elif "Opened" in df.columns:
        df["Created"] = pd.to_datetime(df["Opened"], errors="coerce")
    else:
        df["Created"] = pd.NaT
        st.warning("No column found containing 'Created' or 'Opened'. Aging cannot be calculated.")

    df["Age"] = df["Created"].apply(safe_age)

    if "Client Codes Coding" in df.columns:
        df["Country"] = df["Client Codes Coding"].str[:2]
        df["CompanyCode"] = df["Client Codes Coding"].str[-4:]
    else:
        df["Country"] = ""
        df["CompanyCode"] = ""

    df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3

    pattern = "|".join(["closed", "resolved", "cancel"])
    df["is_open"] = ~df["State"].str.contains(pattern, case=False, na=False)
    return df

def summarize(df):
    return df.groupby("TowerGroup").agg(
        OPEN_TICKETS=("is_open", "sum"),
        Today=("Today", "sum"),
        Yesterday=("Yesterday", "sum"),
        **{"2 Days": ("2 Days", "sum")},
        **{"+3 Days": ("+3 Days", "sum")},
    ).reset_index().rename(columns={"TowerGroup": "TOWER"})

def clean_for_firestore(df):
    df_clean = df.copy()
    for col in df_clean.select_dtypes(include=["datetime", "datetimetz"]).columns:
        df_clean[col] = df_clean[col].apply(lambda x: x if pd.notna(x) else None)
    return df_clean

def upload_to_firestore(df):
    df_clean = clean_for_firestore(df)
    data_json = df_clean.to_dict(orient="records")
    db.collection(COLLECTION_NAME).document(DOCUMENT_ID).set({
        "data": data_json,
        "last_update": dt.datetime.utcnow()
    })

def download_from_firestore():
    doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
    if doc.exists:
        content = doc.to_dict()
        return pd.DataFrame(content["data"]), content.get("last_update")
    return pd.DataFrame(), None

def to_excel(df):
    df_safe = df.copy()
    for col in df_safe.columns:
        df_safe[col] = df_safe[col].apply(lambda x: str(x) if isinstance(x, (dict, list, set)) else x)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_safe.to_excel(writer, index=False, sheet_name="Data")
    return output.getvalue()

# Estado inicial
if "admin" not in st.session_state:
    st.session_state.admin = False

st.title("📈 Tickets Aging Dashboard")

refresh = st.button("🔄 Refresh Database")

# Modo administrador
with st.expander("🔐 Administrator Access"):
    if not st.session_state.admin:
        pwd = st.text_input("Enter ADMIN Code", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Admin mode enabled ✅")
    else:
        uploaded = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
        if uploaded:
            df_new = load_data_from_excel(uploaded)
            upload_to_firestore(df_new)
            st.success("Database updated successfully ✅")
            st.rerun()

if refresh:
    st.experimental_rerun()

df, last_update = download_from_firestore()

if not df.empty:
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    df["Age"] = df["Created"].apply(safe_age)
    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3
    if "TowerGroup" not in df.columns:
        df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)

    # Filtros
    st.sidebar.header("Filters")
    countries = sorted(df["Country"].dropna().unique())
    companies = sorted(df["CompanyCode"].dropna().unique())

    sel_country = st.sidebar.multiselect("Country", countries, default=countries)
    sel_company = st.sidebar.multiselect("Company Code", companies, default=companies)

    df_filtered = df[
        df["Country"].isin(sel_country) &
        df["CompanyCode"].isin(sel_company) &
        df["TowerGroup"].isin(ALLOWED_TOWERS)
    ]

    summary = summarize(df_filtered)

    st.sidebar.header("Graph Filters")
    sel_towers = st.sidebar.multiselect("Select Towers", summary["TOWER"].unique(), default=summary["TOWER"].unique())

    df_graph = df_filtered[df_filtered["TowerGroup"].isin(sel_towers)]
    summary_filtered = summary[summary["TOWER"].isin(sel_towers)]

    if not df_graph.empty:
        st.subheader("📊 KPIs")
        total_open = int(df_graph["is_open"].sum())
        total_plus3 = int(df_graph["+3 Days"].sum())
        percent_overdue = (total_plus3 / total_open) * 100 if total_open > 0 else 0

        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("🎫 Open Tickets", total_open)
        kpi2.metric("🕑 +3 Days", total_plus3)
        kpi3.metric("📈 % Overdue", f"{percent_overdue:.1f}%")
        if percent_overdue > 30:
            st.warning("⚠️ High Overdue Rate! Please check aging tickets.")

        st.subheader("📋 Summary by Tower")
        st.dataframe(summary_filtered, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            if summary_filtered["OPEN_TICKETS"].sum() > 0:
                fig1, ax1 = plt.subplots()
                ax1.pie(summary_filtered["OPEN_TICKETS"], labels=summary_filtered["TOWER"], autopct='%1.1f%%')
                ax1.axis('equal')
                st.pyplot(fig1)
            else:
                st.warning("No data for Open Tickets chart.")

        with col2:
            if summary_filtered["+3 Days"].sum() > 0:
                fig2, ax2 = plt.subplots()
                ax2.pie(summary_filtered["+3 Days"], labels=summary_filtered["TOWER"], autopct='%1.1f%%')
                ax2.axis('equal')
                st.pyplot(fig2)
            else:
                st.warning("No data for +3 Days chart.")

        st.subheader("📋 Status Overview")
        status_summary = df_graph["State"].value_counts().reset_index()
        status_summary.columns = ["Status", "Count"]
        st.dataframe(status_summary, use_container_width=True, hide_index=True)

        st.subheader("📥 Download Full Data")
        st.download_button(
            label="Download Filtered DB",
            data=to_excel(df_graph),
            file_name="Filtered_Tickets.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.subheader("👁️ Ticket Drilldown")
        selected_tower = st.selectbox("Select a Tower", df_graph["TowerGroup"].unique())
        with st.expander(f"📂 View tickets in {selected_tower}"):
            df_tower = df_graph[df_graph["TowerGroup"] == selected_tower]
            filter_state = st.multiselect("Filter by Status", df_tower["State"].unique())
            if filter_state:
                df_tower = df_tower[df_tower["State"].isin(filter_state)]
            st.dataframe(df_tower, use_container_width=True)

            st.download_button(
                label="Download Drilldown Tickets",
                data=to_excel(df_tower),
                file_name=f"Tickets_{selected_tower}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.subheader("📅 Last Ticket Created")
        last_created = df_graph["Created"].max()
        st.info(f"Last Ticket Date: {last_created.strftime('%Y-%m-%d') if pd.notna(last_created) else '–'}")
    else:
        st.warning("No data available for selected filters.")

footer = f"Last update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}" if last_update else "Last update: –"
st.markdown(
    f"""
    <div style="position:fixed; bottom:0; left:0; width:100%; text-align:center;
    padding:6px; font-size:0.75rem; color:#888; background-color:#f8f8f8;">
    {footer}
    </div>
    """,
    unsafe_allow_html=True
)
