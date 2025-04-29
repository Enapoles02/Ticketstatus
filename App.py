# app.py
import streamlit as st
import pandas as pd
import datetime as dt
import json
import firebase_admin
from firebase_admin import credentials, firestore
import io
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="TICKETS DASHBOARD",
    page_icon="📈",
    layout="wide",
)

ADMIN_CODE = "ADMIN"
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"
ALLOWED_TOWERS = ["MDM", "P2P", "O2C", "R2R"]

if not firebase_admin._apps:
    firebase_credentials = json.loads(st.secrets["firebase_credentials"])
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()


def load_data_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    today = pd.Timestamp("today").normalize()
    df["Age"] = (today - df["Created"].dt.normalize()).dt.days
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
    agg = df.groupby("TowerGroup").agg(
        OPEN_TICKETS=("is_open", "sum"),
        Today=("Today", "sum"),
        Yesterday=("Yesterday", "sum"),
        **{"2 Days": ("2 Days", "sum")},
        **{"+3 Days": ("+3 Days", "sum")},
    ).reset_index()
    agg = agg.rename(columns={"TowerGroup": "TOWER"})
    return agg.sort_values("TOWER")


def upload_to_firestore(df):
    df = df.copy()
    for col in df.columns:
        if "date" in col.lower() or "created" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
        df[col] = df[col].where(df[col].notna(), None)
    data_json = df.to_dict(orient="records")
    db.collection(COLLECTION_NAME).document(DOCUMENT_ID).set({
        "data": data_json,
        "last_update": dt.datetime.utcnow()
    })


def download_from_firestore():
    doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
    if doc.exists:
        content = doc.to_dict()
        df = pd.DataFrame(content["data"])
        return df, content.get("last_update")
    return pd.DataFrame(), None


def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return output.getvalue()


if "admin" not in st.session_state:
    st.session_state.admin = False

st.title("📈 Tickets Aging Dashboard")

with st.expander("🔐 Administrator Access"):
    if not st.session_state.admin:
        pwd = st.text_input("Enter ADMIN Code to enable uploading", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Admin mode enabled ✅")
    else:
        st.info("Admin mode active")
        uploaded = st.file_uploader("Upload a new Excel file", type=["xls", "xlsx"])
        if uploaded:
            df_new = load_data_from_excel(uploaded)
            upload_to_firestore(df_new)
            st.success("Database updated successfully 🔥")
            st.rerun()

df, last_update = download_from_firestore()

if not df.empty:
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    df["Age"] = (pd.Timestamp("today").normalize() - df["Created"].dt.normalize()).dt.days
    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3
    if "TowerGroup" not in df.columns:
        df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    pattern = "|".join(["closed", "resolved", "cancel"])
    df["is_open"] = ~df["State"].str.contains(pattern, case=False, na=False)

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
    sel_towers = st.sidebar.multiselect("Select Towers for Graphs", summary["TOWER"].unique(), default=summary["TOWER"].unique())
    df_graph = df_filtered[df_filtered["TowerGroup"].isin(sel_towers)]
    summary_filtered = summary[summary["TOWER"].isin(sel_towers)]

    if not df_graph.empty:
        st.subheader("📊 Dashboard KPIs")
        total_open = int(df_graph["is_open"].sum())
        total_plus3 = int(df_graph["+3 Days"].sum())
        percent_overdue = (total_plus3 / total_open) * 100 if total_open > 0 else 0

        k1, k2, k3 = st.columns(3)
        k1.metric("🎫 Open Tickets", total_open)
        k2.metric("🕑 +3 Days Tickets", total_plus3)
        k3.metric("📈 % Overdue", f"{percent_overdue:.1f}%")

        st.subheader("📋 Summary by Tower")
        st.dataframe(summary_filtered, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.caption("Open Tickets by Tower")
            fig1, ax1 = plt.subplots()
            ax1.pie(summary_filtered["OPEN_TICKETS"], labels=summary_filtered["TOWER"], autopct='%1.1f%%', startangle=90)
            ax1.axis('equal')
            st.pyplot(fig1)
        with col2:
            st.caption("+3 Days Tickets by Tower")
            fig2, ax2 = plt.subplots()
            ax2.pie(summary_filtered["+3 Days"], labels=summary_filtered["TOWER"], autopct='%1.1f%%', startangle=90)
            ax2.axis('equal')
            st.pyplot(fig2)

        st.subheader("📋 Ticket Status Overview")
        status_summary = df_graph["State"].value_counts().reset_index()
        status_summary.columns = ["Status", "Count"]
        st.dataframe(status_summary, use_container_width=True, hide_index=True)

        st.subheader("📥 Download full filtered database")
        excel_data = to_excel(df_graph)
        st.download_button(
            label="Download Filtered DB",
            data=excel_data,
            file_name="Filtered_Tickets.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.subheader("👁️ Drilldown by Tower")
        selected_tower = st.selectbox("Select a Tower to view details", df_graph["TowerGroup"].unique())
        tower_details = df_graph[df_graph["TowerGroup"] == selected_tower]
        st.dataframe(tower_details, use_container_width=True)

        st.subheader("📅 Last Ticket Created")
        last_created = df_graph["Created"].max()
        st.info(f"Last Ticket Date: {last_created.strftime('%Y-%m-%d') if pd.notna(last_created) else 'No Date Available'}")
    else:
        st.warning("No data available for selected towers.")

footer_text = f"Last update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}" if last_update else "Last update: –"
st.markdown(
    f"""
    <div style="
        position:fixed;
        bottom:0;
        left:0;
        width:100%;
        text-align:center;
        padding:6px;
        font-size:0.75rem;
        color:#aaa;
        background-color:#f9f9f9;
    ">
        {footer_text}
    </div>
    """,
    unsafe_allow_html=True,
)
