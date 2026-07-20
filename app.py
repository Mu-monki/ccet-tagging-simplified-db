import streamlit as st
import pandas as pd

pd.set_option("styler.render.max_elements", 5000000)

# --- PAGE SETUP ---
st.set_page_config(page_title="CCET Data Viewer", layout="wide")
st.title("National CCET Expenditure Data")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    /* Center the spinner and add top/bottom padding */
    div[data-testid="stSpinner"] {
        display: flex;
        justify-content: center;
        padding: 50px 0px !important;
    }
    /* Make the spinner text slightly larger */
    div[data-testid="stSpinner"] p {
        font-size: 1.1rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATA LOADING ---
@st.cache_data(show_spinner="Loading dataset...")
def load_data():
    # Force PAP ID to be read as a string to prevent decimals/scientific notation
    df = pd.read_csv("data-tagged.csv", dtype={"PAP ID": str})
    
    # Rename columns to preferred display headers
    df = df.rename(columns={
        "Fiscal_Year": "FISCAL YEAR",
        "GRIT TAGGING": "INSTITUTION TYPE"
    })
    
    # Ensure numeric types, keeping missing values as NaN for custom styling
    numeric_cols = ["TOTAL", "ADAPTION", "MITIGATION", "FISCAL YEAR"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

df = load_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Data")

def create_filter(label, column_name, is_year=False):
    """Creates a multiselect dropdown with an 'All' option by default."""
    if column_name in df.columns:
        if is_year:
            unique_vals = sorted([str(int(x)) for x in df[column_name].dropna().unique() if x > 0])
        else:
            unique_vals = sorted([str(x) for x in df[column_name].dropna().unique() if str(x).strip() != ""])
            
        options = ["All"] + unique_vals
        return st.sidebar.multiselect(label, options, default=["All"])
    return ["All"]

selected_years = create_filter("Fiscal Year", "FISCAL YEAR", is_year=True)
selected_ngi = create_filter("Institution Type", "INSTITUTION TYPE")
selected_dept = create_filter("Department", "DEPARTMENT")
selected_budget = create_filter("Budget Type", "Type")

# Apply sidebar filters
filtered_df = df.copy()
if "All" not in selected_years and selected_years:
    year_mask = filtered_df["FISCAL YEAR"].dropna().apply(lambda x: str(int(x)))
    filtered_df = filtered_df[filtered_df.index.isin(year_mask[year_mask.isin(selected_years)].index)]
    
if "All" not in selected_ngi and selected_ngi:
    filtered_df = filtered_df[filtered_df["INSTITUTION TYPE"].isin(selected_ngi)]
if "All" not in selected_dept and selected_dept:
    filtered_df = filtered_df[filtered_df["DEPARTMENT"].isin(selected_dept)]
if "All" not in selected_budget and selected_budget:
    filtered_df = filtered_df[filtered_df["Type"].isin(selected_budget)]

# --- OVERALL SUMMARY CONTAINER (Placeholder) ---
# We create a container here so we can populate it AFTER reading the global search input from Tab 1
kpi_container = st.container()

st.markdown("---")

# --- UI TABS ---
tab1, tab2 = st.tabs(["Climate Expenditure Data Table", "Climate Expenditure Aggregated Summary"])

# ==========================================
# TAB 1: INPUTS (Search & Sort Controls)
# ==========================================
with tab1:
    st.subheader("Climate Expenditure Data Table")
    
    search_col, sort_col, order_col = st.columns([2, 1, 1])

    with search_col:
        search_query = st.text_input("Global Search", placeholder="Type keywords...")
    with sort_col:
        sort_column = st.selectbox("Sort Table By", filtered_df.columns.tolist(), index=filtered_df.columns.get_loc("TOTAL") if "TOTAL" in filtered_df.columns else 0)
    with order_col:
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

    show_descriptions = st.checkbox("Show PAP Description and Typology Description columns", value=False)


# ==========================================
# APPLY GLOBAL SEARCH & POPULATE KPIS
# ==========================================
# True Global Search (LIKE %VALUE%) across ALL columns
if search_query.strip():
    search_mask = filtered_df.astype(str).apply(
        lambda col: col.str.contains(search_query, case=False, na=False)
    ).any(axis=1)
    filtered_df = filtered_df[search_mask]

# Populate the KPI container created above with the fully filtered dataset
with kpi_container:
    with st.spinner("Refreshing metrics..."):
        total_budget = filtered_df['TOTAL'].sum(skipna=True) if 'TOTAL' in filtered_df.columns else 0
        total_adapt = filtered_df['ADAPTION'].sum(skipna=True) if 'ADAPTION' in filtered_df.columns else 0
        total_mitig = filtered_df['MITIGATION'].sum(skipna=True) if 'MITIGATION' in filtered_df.columns else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Matching Records", f"{len(filtered_df):,}")
        m2.metric("Total Budget", f"₱ {total_budget:,.2f}")
        m3.metric("Total Adaptation", f"₱ {total_adapt:,.2f}")
        m4.metric("Total Mitigation", f"₱ {total_mitig:,.2f}")


# ==========================================
# TAB 1: RENDER DATA TABLE
# ==========================================
# We append the actual table to tab 1 after the data is fully processed
with tab1:
    with st.spinner("Refreshing data table..."):
        raw_display_df = filtered_df.copy()
            
        raw_display_df = raw_display_df.sort_values(by=sort_column, ascending=(sort_order == "Ascending"))

        if not show_descriptions:
            cols_to_drop = [c for c in ["PAP Description", "TYPOLOGY Description"] if c in raw_display_df.columns]
            raw_display_df = raw_display_df.drop(columns=cols_to_drop)

        # --- CUSTOM TABLE STYLING ---
        money_cols = ["TOTAL", "ADAPTION", "MITIGATION"]
        formatters = {}

        for col in raw_display_df.columns:
            if col in money_cols:
                formatters[col] = lambda x: "None" if pd.isna(x) else f"₱ {x:,.2f}"
            elif col == "FISCAL YEAR":
                formatters[col] = lambda x: "None" if pd.isna(x) else str(int(x))
            else:
                formatters[col] = lambda x: "None" if pd.isna(x) else str(x)

        def style_na(val):
            if pd.isna(val):
                return 'color: red !important; font-style: italic !important; font-weight: normal !important;'
            return ''

        styler = raw_display_df.style.format(formatters)

        try:
            styler = styler.map(style_na)
        except AttributeError:
            styler = styler.applymap(style_na)

        st.dataframe(styler, use_container_width=True, hide_index=True, height=500)


# ==========================================
# TAB 2: AGGREGATED SUMMARY
# ==========================================
with tab2:
    st.subheader("Climate Expenditure Aggregated Summary")
    
    group_mapping = {
        "Department": "DEPARTMENT",
        "Institution Type": "INSTITUTION TYPE",
        "Year": "FISCAL YEAR",
        "Type": "Type",
        "Agency": "AGENCY"
    }
    
    available_groupings = {label: col for label, col in group_mapping.items() if col in filtered_df.columns}
    
    if available_groupings:
        selected_label = st.selectbox("Group Data By:", list(available_groupings.keys()))
        selected_group = available_groupings[selected_label]
        
        with st.spinner("Calculating aggregated summary..."):
            summary_df = filtered_df.groupby(selected_group)[["ADAPTION", "MITIGATION", "TOTAL"]].sum().reset_index()
            summary_df = summary_df.sort_values(by="TOTAL", ascending=False)
            
            top_n = min(3, len(summary_df))
            card_cols = st.columns(top_n)
            for i in range(top_n):
                row = summary_df.iloc[i]
                
                group_label = str(int(row[selected_group])) if selected_group == "FISCAL YEAR" else str(row[selected_group])
                
                with card_cols[i]:
                    st.metric(
                        label=f"Top {i+1}: {group_label[:30]}", 
                        value=f"₱ {row['TOTAL']:,.2f}"
                    )
            
            st.dataframe(
                summary_df.style.format({
                    "ADAPTION": "₱ {:,.2f}", 
                    "MITIGATION": "₱ {:,.2f}", 
                    "TOTAL": "₱ {:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )