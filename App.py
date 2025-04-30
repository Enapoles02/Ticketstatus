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
ALLOWED_TOWERS = ["MDM", "P2P", "O2C", "R2R"]

REGION_MAPPING = {
    "NAMER": ["US", "CA"],
    "LATAM": ["MX", "AR", "PE"],
    "EUR": ["BE", "GB", "ES", "SE", "IT", "FR", "AT", "SK", "RO", "IE", "CH"],
    "AFRICA": ["AO", "ZA"],
    "ASIA / MIDDLE EAST": ["BH", "QA", "AE"]
}

if not firebase_admin._apps:
    raw_credentials = st.secrets["firebase_credentials"]
    firebase_credentials = json.loads(json.dumps(dict(raw_credentials)))
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
    df.columns = df.columns.str.strip()
    created_col = [col for col in df.columns if "created" in col.lower()]
    if created_col:
        df["Created"] = pd.to_datetime(df[created_col[0]], errors="coerce").dt.normalize()
    else:
        df["Created"] = pd.NaT
        st.warning("No 'Created' column found.")

    df["Age"] = df["Created"].apply(safe_age)
    df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)

    if "Assigned to" in df.columns:
        df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].astype(str).str.strip() == "")
    else:
        df["Is_Unassigned"] = False
        st.warning("⚠️ Column 'Assigned to' not found.")

    df["Unassigned_Age"] = df.apply(lambda row: row["Age"] if row["Is_Unassigned"] else None, axis=1)

    if "Client codes coding" in df.columns:
        df["Client codes coding"] = df["Client codes coding"].astype(str)
        df["Country"] = df["Client codes coding"].str[:2]
        df["CompanyCode"] = df["Client codes coding"].str[-4:]
        df["Country_Company"] = df["Country"] + "_" + df["CompanyCode"]

    return df

def summarize(df):
    return df.groupby("TowerGroup").agg(
        OPEN_TICKETS=("is_open", "sum"),
        Today=("Today", "sum"),
        Yesterday=("Yesterday", "sum"),
        **{"2 Days": ("2 Days", "sum")},
        **{"+3 Days": ("+3 Days", "sum")}
    ).reset_index().rename(columns={"TowerGroup": "TOWER"})

def upload_to_firestore(df, batch_size=500):
    df_clean = df.copy()
    for col in df_clean.select_dtypes(include=["datetime", "datetimetz", "datetime64"]).columns:
        df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    for col in df_clean.columns:
        if df_clean[col].apply(lambda x: isinstance(x, (dict, list, set))).any():
            df_clean.drop(columns=[col], inplace=True)
            st.warning(f"⚠️ Dropped column '{col}' (not serializable).")

    total_rows = len(df_clean)
    total_batches = (total_rows + batch_size - 1) // batch_size

    progress_bar = st.progress(0, text="Uploading batches to Firestore...")
    status_text = st.empty()

    try:
        for doc in db.collection(COLLECTION_NAME).stream():
            doc.reference.delete()

        for i in range(total_batches):
            batch_df = df_clean.iloc[i * batch_size : (i + 1) * batch_size]
            db.collection(COLLECTION_NAME).document(f"batch_{i}").set({
                "rows": batch_df.to_dict(orient="records"),
                "timestamp": dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            })
            progress_bar.progress((i + 1) / total_batches, text=f"Uploaded batch {i+1}/{total_batches}")

        db.collection(COLLECTION_NAME).document("meta_info").set({
            "last_update": dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            "total_batches": total_batches,
            "total_rows": total_rows
        })

        progress_bar.empty()
        status_text.success("✅ All batches uploaded successfully!")
    except Exception as e:
        st.error(f"❌ Firestore upload failed:\n\n{e}")

if "Client codes coding" in df.columns:
    df["Client codes coding"] = df["Client codes coding"].astype(str)
    df["Country"] = df["Client codes coding"].str[:2]
    df["CompanyCode"] = df["Client codes coding"].str[-4:]
    df["Country_Company"] = df["Country"] + "_" + df["CompanyCode"]

    region_map = {c: region for region, codes in REGION_MAPPING.items() for c in codes}
    df["Region"] = df["Country"].map(region_map).fillna("Other")
else:
    st.error("❌ 'Client codes coding' column not found in Firestore data.")
    st.stop()

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

# ---- App UI ----
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
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
    df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].astype(str).str.strip() == "")
    df["Unassigned_Age"] = df.apply(lambda row: row["Age"] if row["Is_Unassigned"] else None, axis=1)

    st.sidebar.header("Filters")
    countries = sorted(df["Country"].dropna().unique())
    sel_country = st.sidebar.multiselect("Country", countries, default=countries)

    compatible_companies = df[df["Country"].isin(sel_country)]["CompanyCode"].unique()
    sel_company = st.sidebar.multiselect("Company Code", sorted(compatible_companies), default=sorted(compatible_companies))

    region_map = {c: region for region, codes in REGION_MAPPING.items() for c in codes}
    df["Region"] = df["Country"].map(region_map).fillna("Other")
    sel_region = st.sidebar.multiselect("Region", sorted(set(region_map.values())), default=sorted(set(region_map.values())))

    df_filtered = df[
        df["Country"].isin(sel_country) &
        df["CompanyCode"].isin(sel_company) &
        df["Region"].isin(sel_region) &
        df["TowerGroup"].isin(ALLOWED_TOWERS)
    ]

    summary = summarize(df_filtered)
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

        st.subheader("📋 Unassigned Tickets Overview")
        df_unassigned = df_graph[df_graph["Is_Unassigned"]].copy()
        if not df_unassigned.empty:
            unassigned_summary = df_unassigned.groupby(["TowerGroup", "Unassigned_Age"]).size().unstack(fill_value=0)
            st.bar_chart(unassigned_summary.T)
        else:
            st.success("✅ No unassigned tickets at the moment.")

footer_text = f"""
<div style="position:fixed; bottom:0; left:0; width:100%; text-align:center;
padding:6px; font-size:0.75rem; color:#888; background-color:#f8f8f8;">
Last update: {last_update if last_update else "–"}
</div>
"""
st.markdown(footer_text, unsafe_allow_html=True)
