import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="India Election Results Dashboard",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global chart defaults ──────────────────────────────────────────────────────
FONT       = dict(family="DM Sans, sans-serif", size=16, color="#111111")
GRID_COLOR = "#f0f0f0"
BAR_HEIGHT = 70   # px per bar row

def hbar_layout(n_bars, left_margin=260, right_margin=140, title_x="", title_y="", **kw):
    """Standard layout for every horizontal bar chart."""
    d = dict(
        font=FONT,
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=max(420, n_bars * BAR_HEIGHT),
        margin=dict(l=left_margin, r=right_margin, t=50, b=40),
        xaxis=dict(
            showgrid=True, gridcolor=GRID_COLOR,
            tickfont=dict(size=15, color="#111111", family="DM Sans, sans-serif"), title_font=dict(size=15),
            title=title_x,
        ),
        yaxis=dict(
            tickfont=dict(size=15, color="#1a1a2e", family="DM Sans, sans-serif"),
            title_font=dict(size=15),
            title=title_y, automargin=True,
        ),
        showlegend=False,
    )
    d.update(kw)
    return d

def shorten(name: str, n: int = 32) -> str:
    return name[:n] + "…" if len(name) > n else name

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.main-header { font-family:'Playfair Display',serif; font-size:2.4rem; font-weight:900; color:#ffffff; line-height:1.1; margin-bottom:0; }
.sub-header  { font-size:0.9rem; color:#cbd5e1; margin-top:4px; margin-bottom:1.4rem; }
.kpi-card    { background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%); border-radius:12px; padding:1.1rem 1.4rem; color:white; }
.kpi-label   { font-size:0.72rem; text-transform:uppercase; letter-spacing:1.5px; color:#9ca3af; margin-bottom:4px; }
.kpi-value   { font-family:'Playfair Display',serif; font-size:1.9rem; font-weight:700; color:#f59e0b; line-height:1; }
.kpi-sub     { font-size:0.75rem; color:#6b7280; margin-top:4px; }
.section-title { font-family:'Playfair Display',serif; font-size:1.25rem; font-weight:700; color:#ffffff;
                 border-left:4px solid #f59e0b; padding-left:0.75rem; margin:1.4rem 0 0.8rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Supabase ───────────────────────────────────────────────────────────────────
@st.cache_resource
def get_client():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

@st.cache_data(ttl=300)
def load_filter_options():
    resp = get_client().table("election_results").select("election_year,state,election").execute()
    df = pd.DataFrame(resp.data)
    if not df.empty:
        df["state"]    = df["state"].str.strip()
        df["election"] = df["election"].str.strip()
    return df

@st.cache_data(ttl=300)
def load_data(year, state, election):
    query = (
        get_client().table("election_results").select("*")
        .eq("election_year", year)
        .eq("election", election)
    )
    if state != "All States":
        query = query.eq("state", state)
    resp = query.execute()
    df = pd.DataFrame(resp.data)
    if not df.empty:
        df["constituency"] = df["constituency"].str.strip()
        df["candidate"]    = df["candidate"].str.strip()
        df["party"]        = df["party"].str.strip()
        for c in ["total_votes","evm_votes","postal_votes"]:
            df[c] = df[c].astype(int)
    return df

def compute_winners(df):
    df2 = df.copy()
    df2["rank"] = df2.groupby("constituency")["total_votes"].rank(method="first", ascending=False).astype(int)
    winners = df2[df2["rank"]==1][["constituency","candidate","party","total_votes"]].copy()
    runners = df2[df2["rank"]==2][["constituency","total_votes"]].rename(columns={"total_votes":"runner_up_votes"})
    winners = winners.merge(runners, on="constituency", how="left")
    winners["margin"] = (winners["total_votes"] - winners["runner_up_votes"].fillna(0)).astype(int)
    return winners[["constituency","candidate","party","total_votes","margin"]]

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:1rem 0 1.5rem 0;'>
        <div style='font-size:2.5rem;'>🗳️</div>
        <div style='font-family:Playfair Display,serif;font-size:1.1rem;font-weight:900;color:#1a1a2e;'>Election Results</div>
        <div style='font-size:0.75rem;color:#9ca3af;'>India · Live Dashboard</div>
    </div>""", unsafe_allow_html=True)

    fdf = load_filter_options()
    if fdf.empty:
        st.error("No data found."); st.stop()

    # 1️⃣ Election Type
    all_elections = sorted(fdf["election"].unique())
    sel_election  = st.selectbox("🗂️ Election Type", all_elections)

    # 2️⃣ Year — scoped to election type
    year_options = sorted(fdf[fdf["election"]==sel_election]["election_year"].dropna().unique(), reverse=True)
    sel_year     = st.selectbox("📅 Election Year", year_options)

    # 3️⃣ State — scoped to election type + year
    state_options = sorted(fdf[
        (fdf["election"]==sel_election) &
        (fdf["election_year"]==sel_year)
    ]["state"].unique())

    # Add "All States" only for non-Assembly elections
    is_assembly = "assembly" in sel_election.lower()
    if not is_assembly:
        state_options = ["All States"] + state_options

    sel_state = st.selectbox("🏛️ State", state_options)
    st.divider()
    st.caption("Refreshes every 5 min · Powered by Supabase")

    # ── Admin Upload Section ───────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 🔐 Admin")
    admin_key = st.text_input("Admin Key", type="password", key="admin_key")

    if admin_key and admin_key == st.secrets.get("ADMIN_PASSWORD", st.secrets.get("admin", {}).get("ADMIN_PASSWORD", "")):
        st.success("✓ Admin access granted")
        st.markdown("#### 📤 Upload Election Data")

        uploaded_file = st.file_uploader(
            "Upload Excel (.xlsx)",
            type=["xlsx"],
            help="Expected columns: State, Year, Election, Constituency, Candidate, Party, EVM Votes, Postal Votes, Total Votes"
        )

        if uploaded_file:
            try:
                xl = pd.read_excel(uploaded_file)

                # ── Validate columns ───────────────────────────────────────────
                required_cols = ["State","Year","Election","Constituency","Candidate","Party","EVM Votes","Postal Votes","Total Votes"]
                missing = [c for c in required_cols if c not in xl.columns]
                if missing:
                    st.error(f"Missing columns: {', '.join(missing)}")
                else:
                    # ── Clean incoming data ────────────────────────────────────
                    xl = xl[required_cols].copy()
                    xl.columns = ["state","election_year","election","constituency","candidate","party","evm_votes","postal_votes","total_votes"]
                    for col in ["state","election","constituency","candidate","party"]:
                        xl[col] = xl[col].astype(str).str.strip()
                    for col in ["election_year","evm_votes","postal_votes","total_votes"]:
                        xl[col] = pd.to_numeric(xl[col].astype(str).str.replace("-","0").str.strip(), errors="coerce").fillna(0).astype(int)

                    st.markdown(f"**{len(xl)} rows** found in file across **{xl['state'].nunique()}** state(s), **{xl['election_year'].nunique()}** year(s)")

                    # ── Fetch existing keys from Supabase ──────────────────────
                    with st.spinner("Checking for duplicates..."):
                        existing_resp = get_client().table("election_results")                             .select("election_year,state,election,constituency,candidate")                             .execute()
                        existing_df = pd.DataFrame(existing_resp.data)

                    if not existing_df.empty:
                        for col in ["state","election","constituency","candidate"]:
                            existing_df[col] = existing_df[col].astype(str).str.strip()
                        existing_df["election_year"] = existing_df["election_year"].astype(int)
                        existing_keys = set(
                            zip(existing_df["election_year"], existing_df["state"],
                                existing_df["election"], existing_df["constituency"],
                                existing_df["candidate"])
                        )
                    else:
                        existing_keys = set()

                    # ── Split into new vs duplicate ────────────────────────────
                    xl["_key"] = list(zip(xl["election_year"], xl["state"],
                                          xl["election"], xl["constituency"],
                                          xl["candidate"]))
                    new_rows  = xl[~xl["_key"].isin(existing_keys)].drop(columns=["_key"])
                    dup_rows  = xl[ xl["_key"].isin(existing_keys)].drop(columns=["_key"])

                    # ── Summary ────────────────────────────────────────────────
                    col1, col2 = st.columns(2)
                    col1.metric("✅ New rows to insert", len(new_rows))
                    col2.metric("⚠️ Duplicates (will skip)", len(dup_rows))

                    if len(dup_rows) > 0:
                        with st.expander("View duplicate rows"):
                            st.dataframe(dup_rows[["state","election_year","election","constituency","candidate"]], hide_index=True)

                    if len(new_rows) > 0:
                        if st.button("✅ Confirm & Insert New Rows", type="primary"):
                            with st.spinner(f"Inserting {len(new_rows)} rows..."):
                                try:
                                    records = new_rows.drop(columns=["total_votes"], errors="ignore").to_dict(orient="records")
                                    # Insert in batches of 100
                                    batch_size = 100
                                    inserted = 0
                                    for i in range(0, len(records), batch_size):
                                        batch = records[i:i+batch_size]
                                        get_client().table("election_results").insert(batch).execute()
                                        inserted += len(batch)
                                    st.success(f"✅ Successfully inserted {inserted} rows!")
                                    st.cache_data.clear()
                                except Exception as e:
                                    st.error(f"Insert failed: {e}")
                    else:
                        st.info("No new rows to insert — all data already exists in the database.")

            except Exception as e:
                st.error(f"Error reading file: {e}")

        # ── Alliance Upload ────────────────────────────────────────────────────
        st.markdown("#### 🤝 Upload Alliance Data")
        st.caption("Expected columns: Alliance, Party, Election Year, Election, State, Constituency (last two optional — leave blank for national/party-level)")

        alliance_file = st.file_uploader(
            "Upload Alliance Excel (.xlsx)",
            type=["xlsx"],
            key="alliance_upload"
        )

        if alliance_file:
            try:
                al = pd.read_excel(alliance_file)
                required_al = ["Alliance", "Party", "Election Year", "Election"]
                missing_al  = [c for c in required_al if c not in al.columns]

                if missing_al:
                    st.error(f"Missing columns: {', '.join(missing_al)}")
                else:
                    # Add optional columns if missing
                    if "State"        not in al.columns: al["State"]        = None
                    if "Constituency" not in al.columns: al["Constituency"] = None

                    al = al[["Alliance","Party","Election Year","Election","State","Constituency"]].copy()
                    al.columns = ["alliance_name","party","election_year","election","state","constituency"]
                    al["alliance_name"] = al["alliance_name"].astype(str).str.strip()
                    al["party"]         = al["party"].astype(str).str.strip()
                    al["election"]      = al["election"].astype(str).str.strip()
                    al["election_year"] = pd.to_numeric(al["election_year"], errors="coerce").fillna(0).astype(int)
                    # state & constituency: blank/NaN = None
                    for col in ["state","constituency"]:
                        al[col] = al[col].apply(lambda x: None if pd.isna(x) or str(x).strip() == "" else str(x).strip())

                    st.markdown(f"**{len(al)} rows** found — **{al['alliance_name'].nunique()}** alliance(s), **{al['party'].nunique()}** party(ies)")

                    # Check duplicates
                    with st.spinner("Checking for duplicates..."):
                        ex_resp = get_client().table("alliances")                             .select("alliance_name,party,election_year,election,state,constituency")                             .execute()
                        ex_al = pd.DataFrame(ex_resp.data)

                    if not ex_al.empty:
                        for col in ["state","constituency"]:
                            ex_al[col] = ex_al[col].apply(lambda x: None if pd.isna(x) or x is None else str(x).strip())
                        ex_keys = set(zip(ex_al["alliance_name"], ex_al["party"],
                                         ex_al["election_year"], ex_al["election"],
                                         ex_al["state"].astype(str), ex_al["constituency"].astype(str)))
                    else:
                        ex_keys = set()

                    al["_key"] = list(zip(al["alliance_name"], al["party"],
                                          al["election_year"], al["election"],
                                          al["state"].astype(str), al["constituency"].astype(str)))
                    new_al  = al[~al["_key"].isin(ex_keys)].drop(columns=["_key"])
                    dup_al  = al[ al["_key"].isin(ex_keys)].drop(columns=["_key"])

                    c1, c2 = st.columns(2)
                    c1.metric("✅ New rows to insert", len(new_al))
                    c2.metric("⚠️ Duplicates (will skip)", len(dup_al))

                    if len(dup_al) > 0:
                        with st.expander("View duplicate rows"):
                            st.dataframe(dup_al, hide_index=True)

                    if len(new_al) > 0:
                        if st.button("✅ Confirm & Insert Alliances", type="primary"):
                            with st.spinner(f"Inserting {len(new_al)} rows..."):
                                try:
                                    records = new_al.to_dict(orient="records")
                                    # convert None properly for JSON
                                    for r in records:
                                        if r["state"] == "None" or r["state"] is None:
                                            r["state"] = None
                                        if r.get("constituency") == "None" or r.get("constituency") is None:
                                            r["constituency"] = None
                                    batch_size = 100
                                    inserted   = 0
                                    for i in range(0, len(records), batch_size):
                                        get_client().table("alliances").insert(records[i:i+batch_size]).execute()
                                        inserted += len(records[i:i+batch_size])
                                    st.success(f"✅ Successfully inserted {inserted} alliance rows!")
                                    st.cache_data.clear()
                                except Exception as e:
                                    st.error(f"Insert failed: {e}")
                    else:
                        st.info("No new alliance rows to insert.")

            except Exception as e:
                st.error(f"Error reading alliance file: {e}")

    elif admin_key and admin_key != st.secrets.get("ADMIN_PASSWORD", st.secrets.get("admin", {}).get("ADMIN_PASSWORD", "")):
        st.error("Incorrect key")

# ── Load ───────────────────────────────────────────────────────────────────────
df = load_data(sel_year, sel_state, sel_election)
if df.empty:
    st.warning("No data for selected filters."); st.stop()

winners_df     = compute_winners(df)
total_votes    = df["total_votes"].sum()
n_const        = df["constituency"].nunique()
n_candidates   = df[df["candidate"]!="NOTA"]["candidate"].nunique()
n_parties      = df[df["party"]!="None of the Above"]["party"].nunique()
seats_by_party = winners_df.groupby("party").size()
leading_party  = seats_by_party.idxmax()
seats_leading  = int(seats_by_party.max())

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="main-header">🗳️ {sel_election} · {sel_year} · {sel_state}</div>'
    f'<div class="sub-header">Live results · Supabase · election_results</div>',
    unsafe_allow_html=True,
)

# ── KPIs ───────────────────────────────────────────────────────────────────────
def kpi(col, label, value, sub=""):
    col.markdown(
        f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )

c1,c2,c3,c4,c5 = st.columns(5)
kpi(c1,"Constituencies", str(n_const),                    "total seats")
kpi(c2,"Candidates",     f"{n_candidates:,}",             "excl. NOTA")
kpi(c3,"Parties",        str(n_parties),                  "in the fray")
kpi(c4,"Total Votes",    f"{total_votes/1_00_000:.2f}L",  "lakh votes polled")
kpi(c5,"Leading Party",  str(seats_leading),              f"seats · {shorten(leading_party,20)}")
st.divider()

tab1,tab2,tab3,tab4,tab5 = st.tabs(["🏆  Winners Board","🤝  Alliance View","🎯  Party Performance","🥧  Vote Share","👤  Candidate Comparison"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 · Winners Board
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-title">Constituency-wise Winners</div>', unsafe_allow_html=True)
    disp = winners_df.copy().sort_values("constituency")
    disp.columns = ["Constituency","Winner","Party","Votes","Winning Margin"]
    st.dataframe(
        disp, use_container_width=True, height=500, hide_index=True,
        column_config={
            "Votes": st.column_config.NumberColumn(format="%d"),
            "Winning Margin": st.column_config.ProgressColumn(
                "Winning Margin", min_value=0, max_value=int(disp["Winning Margin"].max()), format="%d"
            ),
        },
    )

    st.markdown('<div class="section-title">Top 15 · Largest Winning Margins</div>', unsafe_allow_html=True)
    tm = disp.nlargest(15,"Winning Margin").copy()
    tm["Party Short"] = tm["Party"].apply(lambda p: shorten(p,30))
    tm = tm.sort_values("Winning Margin", ascending=True)   # bottom = smallest for h-bar

    fig = go.Figure()
    colors = px.colors.qualitative.Bold
    party_color = {p: colors[i % len(colors)] for i, p in enumerate(tm["Party Short"].unique())}
    for _, row in tm.iterrows():
        fig.add_trace(go.Bar(
            x=[row["Winning Margin"]],
            y=[row["Constituency"]],
            orientation="h",
            marker_color=party_color.get(row["Party Short"], "#888"),
            text=f'{row["Winning Margin"]:,}',
            textposition="outside",
            textfont=dict(size=15, color="#1a1a2e"),
            name=row["Party Short"],
            showlegend=False,
            hovertemplate=f"<b>{row['Constituency']}</b><br>Winner: {row['Winner']}<br>Party: {row['Party']}<br>Margin: {row['Winning Margin']:,}<extra></extra>",
        ))
    fig.update_layout(**hbar_layout(
        15, left_margin=200, right_margin=150,
        title_x="Winning Margin (votes)",
    ))
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 · Alliance View
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-title">Alliance-wise Performance</div>', unsafe_allow_html=True)

    @st.cache_data(ttl=300)
    def load_alliances(year, election, state):
        client = get_client()

        # Fetch ALL alliance rows for this year + election in one call
        resp = client.table("alliances").select("*")             .eq("election_year", year).eq("election", election).execute()
        all_df = pd.DataFrame(resp.data)

        if all_df.empty:
            return pd.DataFrame()

        # Ensure constituency column exists
        if "constituency" not in all_df.columns:
            all_df["constituency"] = None

        # Separate by specificity
        const_df = all_df[all_df["constituency"].notna()].copy()
        nat_df   = all_df[all_df["state"].isna() & all_df["constituency"].isna()].copy()

        if state and state != "All States":
            state_df = all_df[(all_df["state"]==state) & all_df["constituency"].isna()].copy()
        else:
            state_df = pd.DataFrame()

        # Build final map: national → overridden by state → overridden by constituency
        # Never map "Independent" at party level — only constituency-specific mappings apply
        nat_df   = nat_df[nat_df["party"] != "Independent"]
        if not state_df.empty:
            state_df = state_df[state_df["party"] != "Independent"]

        final = nat_df[["alliance_name","party","constituency"]].copy()

        if not state_df.empty:
            override_parties = state_df["party"].unique()
            final = final[~final["party"].isin(override_parties)]
            final = pd.concat([final, state_df[["alliance_name","party","constituency"]]], ignore_index=True)

        if not const_df.empty:
            final = pd.concat([final, const_df[["alliance_name","party","constituency"]]], ignore_index=True)

        return final.drop_duplicates()

    alliance_map = load_alliances(sel_year, sel_election, sel_state)

    if alliance_map.empty:
        st.info("No alliance information available.")
    else:
        # ── Merge alliance into main df ────────────────────────────────────────
        adf = df.copy()

        # Split alliance_map into constituency-specific and party-level
        const_map = alliance_map[alliance_map["constituency"].notna()].copy()
        party_map = alliance_map[alliance_map["constituency"].isna()][["alliance_name","party"]].copy()

        # First apply party-level mapping
        adf = adf.merge(party_map, on="party", how="left")

        # Then override with constituency-specific mapping where applicable
        if not const_map.empty:
            const_map = const_map.rename(columns={"alliance_name":"alliance_const"})
            adf = adf.merge(const_map[["alliance_const","party","constituency"]], on=["party","constituency"], how="left")
            adf["alliance_name"] = adf["alliance_const"].combine_first(adf["alliance_name"])
            adf = adf.drop(columns=["alliance_const"])

        adf["alliance_name"] = adf["alliance_name"].fillna("Others / Unallied")

        # ── Winners with alliance ──────────────────────────────────────────────
        adf["rank"] = adf.groupby("constituency")["total_votes"].rank(method="first", ascending=False).astype(int)

        # ── KPI — seats per alliance ───────────────────────────────────────────
        alliance_seats = adf[adf["rank"]==1].groupby("alliance_name").size().sort_values(ascending=False)
        cols = st.columns(min(len(alliance_seats), 4))
        for i, (alliance, seats) in enumerate(alliance_seats.items()):
            if i < 4:
                cols[i].markdown(
                    f'<div class="kpi-card"><div class="kpi-label">{shorten(alliance,20)}</div>'
                    f'<div class="kpi-value">{seats}</div><div class="kpi-sub">seats won</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="section-title">Seats Won by Alliance</div>', unsafe_allow_html=True)

        # ── Seats bar ──────────────────────────────────────────────────────────
        al_seats = (
            adf[adf["rank"]==1].groupby("alliance_name").size()
            .reset_index(name="seats").sort_values("seats", ascending=True)
        )
        fig_al = go.Figure()
        colors_al = px.colors.qualitative.Bold
        for i, (_, row) in enumerate(al_seats.iterrows()):
            fig_al.add_trace(go.Bar(
                x=[row["seats"]],
                y=[row["alliance_name"]],
                orientation="h",
                marker_color=colors_al[i % len(colors_al)],
                text=str(row["seats"]),
                textposition="outside",
                textfont=dict(size=15, color="#111111"),
                showlegend=False,
                hovertemplate=f"<b>{row['alliance_name']}</b><br>Seats: {row['seats']}<extra></extra>",
            ))
        fig_al.update_layout(**hbar_layout(len(al_seats), left_margin=240, right_margin=70, title_x="Seats Won"))
        st.plotly_chart(fig_al, use_container_width=True)

        # ── Alliance Strike Rate table ─────────────────────────────────────────
        st.markdown('<div class="section-title">Alliance Contest & Strike Rate</div>', unsafe_allow_html=True)
        al_stats = []
        for alliance, grp in adf.groupby("alliance_name"):
            contested   = grp["constituency"].nunique()
            won         = (grp["rank"]==1).sum()
            second      = (grp["rank"]==2).sum()
            third       = (grp["rank"]==3).sum()
            others      = int(grp["rank"].gt(3).sum())
            total_votes = grp["total_votes"].sum()
            strike      = round(won/contested*100, 1) if contested else 0
            competitive = round((won+second)/contested*100, 1) if contested else 0
            al_stats.append({
                "Alliance":           alliance,
                "Contested":          contested,
                "Won":                int(won),
                "2nd":                int(second),
                "3rd":                int(third),
                "Others":             others,
                "Strike Rate %":      strike,
                "Competitive Rate %": competitive,
                "Total Votes":        int(total_votes),
            })

        al_stats_df = pd.DataFrame(al_stats).sort_values("Won", ascending=False).reset_index(drop=True)
        st.dataframe(
            al_stats_df, use_container_width=True, hide_index=True, height=300,
            column_config={
                "Alliance":           st.column_config.TextColumn("Alliance",           width="medium"),
                "Contested":          st.column_config.NumberColumn("Contested",        format="%d"),
                "Won":                st.column_config.NumberColumn("Won",              format="%d"),
                "2nd":                st.column_config.NumberColumn("2nd",              format="%d"),
                "3rd":                st.column_config.NumberColumn("3rd",              format="%d"),
                "Others":             st.column_config.NumberColumn("Others",           format="%d"),
                "Strike Rate %":      st.column_config.NumberColumn("Strike Rate %",    format="%.1f%%"),
                "Competitive Rate %": st.column_config.NumberColumn("Competitive Rate %", format="%.1f%%"),
                "Total Votes":        st.column_config.NumberColumn("Total Votes",      format="%d"),
            },
        )

        # ── Party breakdown per alliance ───────────────────────────────────────
        st.markdown('<div class="section-title">Party Breakdown by Alliance</div>', unsafe_allow_html=True)
        for alliance in al_stats_df["Alliance"].tolist():
            with st.expander(f"{alliance}  —  {al_stats_df[al_stats_df['Alliance']==alliance]['Won'].values[0]} seats won"):
                grp = adf[adf["alliance_name"]==alliance]
                pty_stats = []
                for party, pgrp in grp.groupby("party"):
                    pc = pgrp["constituency"].nunique()
                    pw = (pgrp["rank"]==1).sum()
                    p2 = (pgrp["rank"]==2).sum()
                    p3 = (pgrp["rank"]==3).sum()
                    pty_stats.append({
                        "Party":       party,
                        "Contested":   pc,
                        "Won":         int(pw),
                        "2nd":         int(p2),
                        "3rd":         int(p3),
                        "Strike Rate %": round(pw/pc*100,1) if pc else 0,
                        "Total Votes": int(pgrp["total_votes"].sum()),
                    })
                pty_df = pd.DataFrame(pty_stats).sort_values("Won", ascending=False)
                st.dataframe(pty_df, use_container_width=True, hide_index=True,
                    column_config={
                        "Total Votes":    st.column_config.NumberColumn(format="%d"),
                        "Strike Rate %":  st.column_config.NumberColumn(format="%.1f%%"),
                    }
                )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 · Party Performance
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    # Seats won
    st.markdown('<div class="section-title">Seats Won by Party</div>', unsafe_allow_html=True)
    seats = (
        winners_df.groupby("party").size().reset_index(name="seats")
        .sort_values("seats", ascending=True)
    )
    seats["label"] = seats["party"].apply(lambda p: shorten(p, 32))

    fig_s = go.Figure()
    colors = px.colors.qualitative.Bold
    for i, (_, row) in enumerate(seats.iterrows()):
        fig_s.add_trace(go.Bar(
            x=[row["seats"]],
            y=[row["label"]],
            orientation="h",
            marker_color=colors[i % len(colors)],
            text=str(row["seats"]),
            textposition="outside",
            textfont=dict(size=16, color="#1a1a2e"),
            showlegend=False,
            hovertemplate=f"<b>{row['party']}</b><br>Seats: {row['seats']}<extra></extra>",
        ))
    fig_s.update_layout(**hbar_layout(len(seats), left_margin=280, right_margin=80, title_x="Seats Won"))
    st.plotly_chart(fig_s, use_container_width=True)

    # Total votes
    st.markdown('<div class="section-title">Total Votes by Party (Top 15)</div>', unsafe_allow_html=True)
    pv = (
        df[df["party"]!="None of the Above"]
        .groupby("party")["total_votes"].sum().reset_index()
        .sort_values("total_votes", ascending=True).tail(15)
    )
    pv["vote_share"] = (pv["total_votes"] / pv["total_votes"].sum() * 100).round(2)
    pv["label"]      = pv["party"].apply(lambda p: shorten(p, 32))
    pv["text_label"] = pv["total_votes"].apply(lambda x: f"{x/1_00_000:.2f}L")

    fig_v = go.Figure()
    colors2 = px.colors.qualitative.Safe
    for i, (_, row) in enumerate(pv.iterrows()):
        fig_v.add_trace(go.Bar(
            x=[row["total_votes"]],
            y=[row["label"]],
            orientation="h",
            marker_color=colors2[i % len(colors2)],
            text=row["text_label"],
            textposition="outside",
            textfont=dict(size=15, color="#1a1a2e"),
            showlegend=False,
            hovertemplate=f"<b>{row['party']}</b><br>Votes: {row['total_votes']:,}<br>Share: {row['vote_share']:.2f}%<extra></extra>",
        ))
    fig_v.update_layout(**hbar_layout(len(pv), left_margin=280, right_margin=100, title_x="Total Votes"))
    st.plotly_chart(fig_v, use_container_width=True)

    # Summary table
    st.markdown('<div class="section-title">Party Summary</div>', unsafe_allow_html=True)
    summary = pv[["party","total_votes","vote_share"]].merge(seats[["party","seats"]], on="party", how="left").fillna(0)
    summary["seats"] = summary["seats"].astype(int)
    summary = summary.rename(columns={"party":"Party","total_votes":"Total Votes","vote_share":"Vote Share %","seats":"Seats Won"})
    summary = summary.sort_values("Seats Won", ascending=False)
    st.dataframe(
        summary[["Party","Seats Won","Total Votes","Vote Share %"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Total Votes":  st.column_config.NumberColumn(format="%d"),
            "Vote Share %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 · Vote Share
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-title">Overall Vote Share · Top 10 Parties</div>', unsafe_allow_html=True)
        vs = (
            df[df["party"]!="None of the Above"]
            .groupby("party")["total_votes"].sum().reset_index()
            .sort_values("total_votes", ascending=False)
        )
        top10  = vs.head(10).copy()
        others = vs.iloc[10:]["total_votes"].sum()
        if others > 0:
            top10 = pd.concat([top10, pd.DataFrame([{"party":"Others","total_votes":others}])], ignore_index=True)
        top10["party_short"] = top10["party"].apply(lambda p: shorten(p, 20))

        fig_pie = px.pie(top10, values="total_votes", names="party_short",
                         hole=0.42, color_discrete_sequence=px.colors.qualitative.Bold,
                         custom_data=["party"])
        fig_pie.update_traces(
            textposition="inside", textinfo="percent+label",
            textfont=dict(size=14, family="DM Sans, sans-serif"),
            hovertemplate="<b>%{customdata[0]}</b><br>Votes: %{value:,}<br>%{percent}<extra></extra>",
        )
        fig_pie.update_layout(font=FONT, height=480, showlegend=False, margin=dict(l=10,r=10,t=30,b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with right:
        st.markdown('<div class="section-title">EVM vs Postal Votes</div>', unsafe_allow_html=True)
        fig_evm = go.Figure(go.Bar(
            x=["EVM Votes","Postal Votes"],
            y=[df["evm_votes"].sum(), df["postal_votes"].sum()],
            marker_color=["#1a1a2e","#f59e0b"],
            text=[f"{df['evm_votes'].sum()/1_00_000:.2f}L", f"{df['postal_votes'].sum()/1_000:.1f}K"],
            textposition="outside",
            textfont=dict(size=17, color="#1a1a2e"),
        ))
        fig_evm.update_layout(
            font=FONT, plot_bgcolor="white", paper_bgcolor="white", height=480,
            xaxis=dict(tickfont=dict(size=17, color="#111111", family="DM Sans, sans-serif"), title=""),
            yaxis=dict(title="Votes", showgrid=True, gridcolor=GRID_COLOR, tickfont=dict(size=15, color="#111111", family="DM Sans, sans-serif")),
            margin=dict(l=20,r=20,t=40,b=20),
        )
        st.plotly_chart(fig_evm, use_container_width=True)

    st.markdown('<div class="section-title">Party Contest & Strike Rate</div>', unsafe_allow_html=True)

    # ── Compute ranks per constituency ─────────────────────────────────────────
    ranked = df.copy()
    ranked["rank"] = ranked.groupby("constituency")["total_votes"].rank(method="first", ascending=False).astype(int)

    # ── Aggregate per party ────────────────────────────────────────────────────
    party_stats = []
    for party, grp in ranked.groupby("party"):
        contested   = len(grp)
        won         = (grp["rank"] == 1).sum()
        second      = (grp["rank"] == 2).sum()
        third       = (grp["rank"] == 3).sum()
        others      = contested - won - second - third
        total_votes = grp["total_votes"].sum()
        strike      = round(won / contested * 100, 1) if contested > 0 else 0
        competitive = round((won + second) / contested * 100, 1) if contested > 0 else 0
        party_stats.append({
            "Party":            party,
            "Contested":        contested,
            "Won":              int(won),
            "2nd":              int(second),
            "3rd":              int(third),
            "Others":           int(others),
            "Strike Rate %":    strike,
            "Competitive Rate %": competitive,
            "Total Votes":      int(total_votes),
        })

    stats_df = pd.DataFrame(party_stats).sort_values("Won", ascending=False).reset_index(drop=True)

    st.dataframe(
        stats_df,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "Party":              st.column_config.TextColumn("Party",              width="large"),
            "Contested":          st.column_config.NumberColumn("Contested",        format="%d"),
            "Won":                st.column_config.NumberColumn("Won",              format="%d"),
            "2nd":                st.column_config.NumberColumn("2nd",              format="%d"),
            "3rd":                st.column_config.NumberColumn("3rd",              format="%d"),
            "Others":             st.column_config.NumberColumn("Others",           format="%d"),
            "Strike Rate %":      st.column_config.NumberColumn("Strike Rate %",    format="%.1f%%"),
            "Competitive Rate %": st.column_config.NumberColumn("Competitive Rate %", format="%.1f%%"),
            "Total Votes":        st.column_config.NumberColumn("Total Votes",      format="%d"),
        },
    )
    st.caption(f"Sorted by Won (descending) · {len(stats_df)} parties · Click any column header to re-sort")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 · Candidate Comparison
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-title">Candidate-wise Results by Constituency</div>', unsafe_allow_html=True)
    sel_const   = st.selectbox("Select Constituency", sorted(df["constituency"].unique()), key="cand_const")
    cand_df     = df[df["constituency"]==sel_const].sort_values("total_votes", ascending=True).copy()
    winner_name = cand_df.iloc[-1]["candidate"]

    cand_df["share"] = (cand_df["total_votes"] / cand_df["total_votes"].sum() * 100).round(1)

    fig_cand = go.Figure()
    for _, row in cand_df.iterrows():
        is_w  = row["candidate"] == winner_name
        # Two-line Y-axis: candidate on top, party below
        label = f"{'🏆 ' if is_w else ''}{row['candidate']}<br><i>{shorten(row['party'], 40)}</i>"
        fig_cand.add_trace(go.Bar(
            x=[row["total_votes"]],
            y=[label],
            orientation="h",
            marker_color="#f59e0b" if is_w else "#1a1a2e",
            text=f"{row['total_votes']:,} ({row['share']:.1f}%)",
            textposition="auto",
            textfont=dict(size=14, color="#111111"),
            insidetextfont=dict(size=14, color="#ffffff"),
            showlegend=False,
            hovertemplate=(
                f"<b>{row['candidate']}</b><br>Party: {row['party']}<br>"
                f"EVM: {row['evm_votes']:,}<br>Postal: {row['postal_votes']:,}<br>"
                f"Total: {row['total_votes']:,} ({row['share']:.1f}%)<extra></extra>"
            ),
        ))
    fig_cand.update_layout(**hbar_layout(len(cand_df), left_margin=440, right_margin=40, title_x="Total Votes"))
    st.plotly_chart(fig_cand, use_container_width=True)

    total_c = cand_df["total_votes"].sum()
    w_row   = cand_df[cand_df["candidate"]==winner_name].iloc[0]
    r_row   = cand_df.sort_values("total_votes", ascending=False).iloc[1]
    margin  = int(w_row["total_votes"]) - int(r_row["total_votes"])

    m1,m2,m3 = st.columns(3)
    m1.metric("🏆 Winner",         w_row["candidate"],  w_row["party"])
    m2.metric("📊 Winning Margin", f"{margin:,} votes", f"{margin/total_c*100:.1f}% of total")
    m3.metric("🗳️ Total Votes",    f"{total_c:,}",      f"{len(cand_df)} candidates")
