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

if not firebase_admin._apps:
    raw_secrets = st.secrets["firebase_credentials"]
    firebase_credentials = {k: v for k, v in raw_secrets.items()}
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

def safe_age(created_date):
    try:
        if pd.isna(created_date):
            return None
        created = pd.to_datetime(created_date).tz_localize(None)
        today = pd.Timestamp("today").normalize()
        return (today - created.normalize()).days
    except Exception:
        return None

def load_data_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip().str.replace(r"[\r\n]+", "", regex=True)
    created_col = [col for col in df.columns if "created" in col.lower()]
    df["Created"] = pd.to_datetime(df[created_col[0]], errors="coerce").dt.normalize() if created_col else pd.NaT
    df["Age"] = df["Created"].apply(safe_age)
    df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()

    if "Client Codes Coding" in df.columns:
        df["Country"] = df["Client Codes Coding"].astype(str).str[:2]
        df["CompanyCode"] = df["Client Codes Coding"].astype(str).str[-4:]
    else:
        df["Country"] = None
        df["CompanyCode"] = None
        st.warning("⚠️ 'Client Codes Coding' column is missing. 'Country' and 'CompanyCode' not derived.")

    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
    df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].astype(str).str.strip() == "")
    df["Unassigned_Age"] = df.apply(lambda row: row["Age"] if row["Is_Unassigned"] else None, axis=1)
    return df

def summarize(df):
    return df.groupby("TowerGroup").agg(
        OPEN_TICKETS=("is_open", "sum"),
        Today=("Today", "sum"),
        Yesterday=("Yesterday", "sum"),
        **{"2 Days": ("2 Days", "sum")},
        **{"+3 Days": ("+3 Days", "sum")}
    ).reset_index().rename(columns={"TowerGroup": "TOWER"})

def upload_to_firestore(df):
    df_clean = df.copy()
    for col in df_clean.select_dtypes(include=["datetime", "datetimetz", "datetime64"]).columns:
        df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    for col in df_clean.columns:
        if df_clean[col].apply(lambda x: isinstance(x, (dict, list, set))).any():
            df_clean.drop(columns=[col], inplace=True)
            st.warning(f"⚠️ Dropped column '{col}' (not serializable).")
    data_json = df_clean.to_dict(orient="records")
    db.collection(COLLECTION_NAME).document(DOCUMENT_ID).set({
        "data": data_json,
        "last_update": dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })

def download_from_firestore():
    doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
    if doc.exists:
        content = doc.to_dict()
        return pd.DataFrame(content["data"]), content.get("last_update")
    return pd.DataFrame(), None

def to_excel(df):
    df_safe = df.copy()
    for col in df_safe.select_dtypes(include=["datetimetz"]).columns:
        df_safe[col] = df_safe[col].dt.tz_localize(None)
    for col in df_safe.columns:
        df_safe[col] = df_safe[col].apply(lambda x: str(x) if isinstance(x, (dict, list, set)) else x)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_safe.to_excel(writer, index=False, sheet_name="Data")
    return output.getvalue()

if "admin" not in st.session_state:
    st.session_state.admin = False

st.title("📈 Tickets Aging Dashboard")
refresh = st.button("🔄 Refresh Database")

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
    st.rerun()

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
    if "Country" not in df.columns and "Client Codes Coding" in df.columns:
        df["Country"] = df["Client Codes Coding"].astype(str).str[:2]
        df["CompanyCode"] = df["Client Codes Coding"].astype(str).str[-4:]
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
    df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].astype(str).str.strip() == "")
    df["Unassigned_Age"] = df.apply(lambda row: row["Age"] if row["Is_Unassigned"] else None, axis=1)

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

        st.subheader("📋 Summary by Tower")
        st.dataframe(summary_filtered, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🔵 Open Tickets Distribution by Tower**")
            fig1, ax1 = plt.subplots()
            ax1.pie(summary_filtered["OPEN_TICKETS"], labels=summary_filtered["TOWER"], autopct='%1.1f%%')
            ax1.axis('equal')
            st.pyplot(fig1)

        with col2:
            st.markdown("**🟠 Tickets Aged +3 Days by Tower**")
            fig2, ax2 = plt.subplots()
            ax2.pie(summary_filtered["+3 Days"], labels=summary_filtered["TOWER"], autopct='%1.1f%%')
            ax2.axis('equal')
            st.pyplot(fig2)

        st.subheader("📋 Status Overview by Tower")
        pivot_status = df_graph.pivot_table(index="State", columns="TowerGroup", values="Created", aggfunc="count", fill_value=0).astype(int)
        st.dataframe(pivot_status, use_container_width=True)

        st.subheader("📥 Download Full Data")
        st.download_button("Download Filtered DB", data=to_excel(df_graph), file_name="Filtered_Tickets.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.subheader("👁️ Ticket Drilldown")
        selected_tower = st.selectbox("Select a Tower", df_graph["TowerGroup"].unique())
        df_tower = df_graph[df_graph["TowerGroup"] == selected_tower]
        filter_state = st.multiselect("Filter by Status", df_tower["State"].unique())
        if filter_state:
            df_tower = df_tower[df_tower["State"].isin(filter_state)]
        st.dataframe(df_tower, use_container_width=True)
        st.download_button("Download Drilldown Tickets", data=to_excel(df_tower), file_name=f"Tickets_{selected_tower}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.subheader("📋 Unassigned Tickets Overview")
        df_unassigned = df_graph[df_graph["Is_Unassigned"]].copy()
        if not df_unassigned.empty:
            df_unassigned = df_unassigned.sort_values("Unassigned_Age", ascending=False)
            st.dataframe(df_unassigned[["Number", "Short description", "Created", "Age", "Unassigned_Age"]], use_container_width=True, hide_index=True)
            overdue_unassigned = df_unassigned[df_unassigned["Unassigned_Age"] > 3].shape[0]
            if overdue_unassigned > 0:
                st.error(f"⚠️ {overdue_unassigned} tickets have been unassigned for more than 3 days! Immediate action required.")

        st.subheader("👁️ Unassigned Ticket Drilldown")
        if not df_unassigned.empty:
            filter_state_unassigned = st.multiselect("Filter by Status (Unassigned)", df_unassigned["State"].unique())
            if filter_state_unassigned:
                df_unassigned = df_unassigned[df_unassigned["State"].isin(filter_state_unassigned)]
            st.dataframe(df_unassigned, use_container_width=True)
            st.download_button("Download Unassigned Tickets", data=to_excel(df_unassigned), file_name="Unassigned_Tickets.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("No data available for selected filters.")

footer_text = f"""
    <div style="position:fixed; bottom:0; left:0; width:100%; text-align:center;
    padding:6px; font-size:0.75rem; color:#888; background-color:#f8f8f8;">
    Last update: {last_update if isinstance(last_update, str) else (last_update.strftime('%Y-%m-%d %H:%M:%S') if last_update else "–")}
    </div>
"""
st.markdown(footer_text, unsafe_allow_html=True)

st.subheader("🌍 Tickets by Region and Country (Interactive)")
import altair as alt
if "Region" not in df_graph.columns:
    REGION_MAPPING = {
        "NAMER": ["US", "CA"],
        "LATAM": ["MX", "AR", "PE"],
        "EUR": ["BE", "GB", "ES", "SE", "IT", "FR", "AT", "SK", "RO", "IE", "CH"],
        "AFRICA": ["AO", "ZA"],
        "ASIA / MIDDLE EAST": ["BH", "QA", "AE"]
    }
    region_lookup = {code: region for region, codes in REGION_MAPPING.items() for code in codes}
    df_graph["Region"] = df_graph["Country"].map(region_lookup).fillna("Other")

alt_data = df_graph.groupby(["Region", "Country"]).size().reset_index(name="Ticket Count")
chart = alt.Chart(alt_data).mark_bar().encode(
    x=alt.X('Country:N', sort='-y'),
    y='Ticket Count:Q',
    color='Region:N',
    tooltip=['Region:N', 'Country:N', 'Ticket Count:Q']
).interactive().properties(width=700, height=400)
st.altair_chart(chart, use_container_width=True)

