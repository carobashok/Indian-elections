#python -m streamlit run election_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
import warnings
warnings.filterwarnings("ignore")

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="India Election Results Dashboard",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.main-header {
    font-family: 'Playfair Display', serif;
    font-size: 2.6rem;
    font-weight: 900;
    color: #1a1a2e;
    line-height: 1.1;
    margin-bottom: 0;
}
.sub-header {
    font-size: 0.95rem;
    color: #6b7280;
    margin-top: 4px;
    margin-bottom: 1.5rem;
}
.kpi-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    color: white;
}
.kpi-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #9ca3af;
    margin-bottom: 4px;
}
.kpi-value {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    font-weight: 700;
    color: #f59e0b;
    line-height: 1;
}
.kpi-sub {
    font-size: 0.78rem;
    color: #6b7280;
    margin-top: 4px;
}
.section-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.3rem;
    font-weight: 700;
    color: #1a1a2e;
    border-left: 4px solid #f59e0b;
    padding-left: 0.75rem;
    margin: 1.5rem 0 1rem 0;
}
</style>
""", unsafe_allow_html=True)


# ── Supabase connection ────────────────────────────────────────────────────────
@st.cache_resource
def get_client():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_filter_options() -> pd.DataFrame:
    """Distinct year / state / election combos for cascading filters."""
    client = get_client()
    resp = client.table("election_results").select("election_year, state, election").execute()
    df = pd.DataFrame(resp.data)
    if not df.empty:
        df["state"]    = df["state"].str.strip()
        df["election"] = df["election"].str.strip()
    return df


@st.cache_data(ttl=300)
def load_data(year: int, state: str, election: str) -> pd.DataFrame:
    client = get_client()
    resp = (
        client.table("election_results")
        .select("*")
        .eq("election_year", year)
        .eq("state", state)
        .eq("election", election)
        .execute()
    )
    df = pd.DataFrame(resp.data)
    if not df.empty:
        df["constituency"] = df["constituency"].str.strip()
        df["candidate"]    = df["candidate"].str.strip()
        df["party"]        = df["party"].str.strip()
        for col in ["total_votes", "evm_votes", "postal_votes"]:
            df[col] = df[col].astype(int)
    return df


# ── Winner computation ─────────────────────────────────────────────────────────
def compute_winners(df: pd.DataFrame) -> pd.DataFrame:
    ranked   = df.sort_values("total_votes", ascending=False)
    winners  = ranked.groupby("constituency").first().reset_index()
    runner   = (
        ranked.groupby("constituency")
        .nth(1)["total_votes"]
        .reset_index()
        .rename(columns={"total_votes": "runner_up_votes"})
    )
    winners  = winners.merge(runner, on="constituency", how="left")
    winners["margin"] = (winners["total_votes"] - winners["runner_up_votes"].fillna(0)).astype(int)
    return winners[["constituency", "candidate", "party", "total_votes", "margin"]]


# ── Sidebar filters ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding:1rem 0 1.5rem 0;'>
        <div style='font-size:2.5rem;'>🗳️</div>
        <div style='font-family:Playfair Display,serif; font-size:1.1rem;
                    font-weight:900; color:#1a1a2e;'>Election Results</div>
        <div style='font-size:0.75rem; color:#9ca3af;'>India · Live Dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    filter_df = load_filter_options()

    if filter_df.empty:
        st.error("No data in election_results table.")
        st.stop()

    # Year
    years    = sorted(filter_df["election_year"].dropna().unique(), reverse=True)
    sel_year = st.selectbox("📅 Election Year", years)

    # State — scoped to year
    states    = sorted(filter_df[filter_df["election_year"] == sel_year]["state"].unique())
    sel_state = st.selectbox("🏛️ State", states)

    # Election type — scoped to year + state
    elections    = sorted(
        filter_df[
            (filter_df["election_year"] == sel_year) &
            (filter_df["state"]         == sel_state)
        ]["election"].unique()
    )
    sel_election = st.selectbox("🗂️ Election Type", elections)

    st.divider()
    st.caption("Refreshes every 5 min · Powered by Supabase")


# ── Load data ──────────────────────────────────────────────────────────────────
df = load_data(sel_year, sel_state, sel_election)

if df.empty:
    st.warning("No data found for the selected filters.")
    st.stop()

winners_df = compute_winners(df)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="main-header">🗳️ {sel_state} · {sel_election} · {sel_year}</div>'
    f'<div class="sub-header">Live results · Supabase · election_results table</div>',
    unsafe_allow_html=True,
)

# ── KPI row ────────────────────────────────────────────────────────────────────
total_votes   = df["total_votes"].sum()
n_const       = df["constituency"].nunique()
n_candidates  = df[df["candidate"] != "NOTA"]["candidate"].nunique()
n_parties     = df[df["party"] != "None of the Above"]["party"].nunique()
seats_by_party = winners_df.groupby("party").size()
leading_party  = seats_by_party.idxmax()
seats_leading  = seats_by_party.max()

def kpi_card(col, label, value, sub=""):
    col.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

c1, c2, c3, c4, c5 = st.columns(5)
kpi_card(c1, "Constituencies",  str(n_const),                       "total seats")
kpi_card(c2, "Candidates",      f"{n_candidates:,}",                "excl. NOTA")
kpi_card(c3, "Parties",         str(n_parties),                     "in the fray")
kpi_card(c4, "Total Votes",     f"{total_votes/1_00_000:.2f}L",     "lakh votes polled")
kpi_card(c5, "Leading Party",   str(seats_leading),                 f"seats · {leading_party[:22]}")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🏆  Winners Board",
    "🎯  Party Performance",
    "🥧  Vote Share",
    "👤  Candidate Comparison",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 · Winners Board
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-title">Constituency-wise Winners</div>', unsafe_allow_html=True)

    disp = winners_df.copy().sort_values("constituency")
    disp.columns = ["Constituency", "Winner", "Party", "Votes", "Winning Margin"]

    st.dataframe(
        disp,
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={
            "Votes":          st.column_config.NumberColumn(format="%d"),
            "Winning Margin": st.column_config.ProgressColumn(
                "Winning Margin",
                min_value=0,
                max_value=int(disp["Winning Margin"].max()),
                format="%d",
            ),
        },
    )

    st.markdown('<div class="section-title">Top 15 · Largest Winning Margins</div>', unsafe_allow_html=True)
    top_margin = disp.nlargest(15, "Winning Margin")
    fig = px.bar(
        top_margin, x="Winning Margin", y="Constituency",
        orientation="h", color="Party", text="Winning Margin",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(
        height=480, plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
        xaxis=dict(showgrid=True, gridcolor="#f3f4f6"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=40, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 · Party Performance
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-title">Seats Won by Party</div>', unsafe_allow_html=True)

    seats = (
        winners_df.groupby("party").size()
        .reset_index(name="seats")
        .sort_values("seats", ascending=False)
    )
    fig_s = px.bar(
        seats, x="party", y="seats", color="party", text="seats",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig_s.update_traces(textposition="outside")
    fig_s.update_layout(
        height=420, plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
        xaxis=dict(title="", tickangle=-35, tickfont=dict(size=10)),
        yaxis=dict(title="Seats Won", showgrid=True, gridcolor="#f3f4f6"),
        margin=dict(l=10, r=10, t=10, b=120),
    )
    st.plotly_chart(fig_s, use_container_width=True)

    st.markdown('<div class="section-title">Total Votes by Party (Top 15)</div>', unsafe_allow_html=True)

    party_votes = (
        df[df["party"] != "None of the Above"]
        .groupby("party")["total_votes"].sum()
        .reset_index()
        .sort_values("total_votes", ascending=False)
        .head(15)
    )
    party_votes["vote_share"] = (party_votes["total_votes"] / party_votes["total_votes"].sum() * 100).round(2)
    party_votes["label"]      = party_votes["total_votes"].apply(lambda x: f"{x/1_00_000:.2f}L")

    fig_v = px.bar(
        party_votes, x="party", y="total_votes", color="party", text="label",
        hover_data={"vote_share": ":.2f"},
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig_v.update_traces(textposition="outside")
    fig_v.update_layout(
        height=420, plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
        xaxis=dict(title="", tickangle=-35, tickfont=dict(size=10)),
        yaxis=dict(title="Total Votes", showgrid=True, gridcolor="#f3f4f6"),
        margin=dict(l=10, r=10, t=10, b=120),
    )
    st.plotly_chart(fig_v, use_container_width=True)

    st.markdown('<div class="section-title">Party Summary</div>', unsafe_allow_html=True)
    summary = party_votes.merge(seats, on="party", how="left").fillna(0)
    summary["seats"] = summary["seats"].astype(int)
    summary = summary.rename(columns={
        "party": "Party", "total_votes": "Total Votes",
        "vote_share": "Vote Share %", "seats": "Seats Won",
    }).sort_values("Seats Won", ascending=False)
    st.dataframe(
        summary[["Party", "Seats Won", "Total Votes", "Vote Share %"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Total Votes":  st.column_config.NumberColumn(format="%d"),
            "Vote Share %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 · Vote Share
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-title">Overall Vote Share · Top 10 Parties</div>', unsafe_allow_html=True)
        vs = (
            df[df["party"] != "None of the Above"]
            .groupby("party")["total_votes"].sum()
            .reset_index()
            .sort_values("total_votes", ascending=False)
        )
        top10  = vs.head(10)
        others = vs.iloc[10:]["total_votes"].sum()
        if others > 0:
            top10 = pd.concat(
                [top10, pd.DataFrame([{"party": "Others", "total_votes": others}])],
                ignore_index=True,
            )
        fig_pie = px.pie(
            top10, values="total_votes", names="party",
            hole=0.45, color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
        fig_pie.update_layout(height=420, showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with right:
        st.markdown('<div class="section-title">EVM vs Postal Votes</div>', unsafe_allow_html=True)
        fig_evm = go.Figure(go.Bar(
            x=["EVM Votes", "Postal Votes"],
            y=[df["evm_votes"].sum(), df["postal_votes"].sum()],
            marker_color=["#1a1a2e", "#f59e0b"],
            text=[
                f"{df['evm_votes'].sum()/1_00_000:.2f}L",
                f"{df['postal_votes'].sum()/1_000:.1f}K",
            ],
            textposition="outside",
        ))
        fig_evm.update_layout(
            height=420, plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Votes"),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig_evm, use_container_width=True)

    st.markdown('<div class="section-title">Constituency-level Vote Share</div>', unsafe_allow_html=True)
    sel_const_vs = st.selectbox("Select Constituency", sorted(df["constituency"].unique()), key="vs_const")
    c_df = df[df["constituency"] == sel_const_vs].sort_values("total_votes", ascending=False).copy()
    c_df["share"] = (c_df["total_votes"] / c_df["total_votes"].sum() * 100).round(2)

    fig_cv = px.bar(
        c_df, x="candidate", y="total_votes", color="party", text="share",
        color_discrete_sequence=px.colors.qualitative.Bold,
        hover_data={"evm_votes": True, "postal_votes": True},
    )
    fig_cv.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_cv.update_layout(
        height=400, plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(title="", tickangle=-30, tickfont=dict(size=10)),
        yaxis=dict(title="Votes", showgrid=True, gridcolor="#f3f4f6"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
        margin=dict(l=10, r=10, t=40, b=80),
    )
    st.plotly_chart(fig_cv, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 · Candidate Comparison
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-title">Candidate-wise Results by Constituency</div>', unsafe_allow_html=True)

    sel_const = st.selectbox("Select Constituency", sorted(df["constituency"].unique()), key="cand_const")
    cand_df   = df[df["constituency"] == sel_const].sort_values("total_votes", ascending=True).copy()
    winner_name = cand_df.iloc[-1]["candidate"]

    fig_cand = go.Figure()
    for _, row in cand_df.iterrows():
        color = "#f59e0b" if row["candidate"] == winner_name else "#1a1a2e"
        fig_cand.add_trace(go.Bar(
            x=[row["total_votes"]],
            y=[f"{row['candidate']} ({row['party'][:18]})"],
            orientation="h",
            marker_color=color,
            text=f"{row['total_votes']:,}",
            textposition="outside",
            showlegend=False,
            hovertemplate=(
                f"<b>{row['candidate']}</b><br>"
                f"Party: {row['party']}<br>"
                f"EVM: {row['evm_votes']:,}<br>"
                f"Postal: {row['postal_votes']:,}<br>"
                f"Total: {row['total_votes']:,}<extra></extra>"
            ),
        ))

    fig_cand.update_layout(
        height=max(400, len(cand_df) * 48),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(title="Total Votes", showgrid=True, gridcolor="#f3f4f6"),
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(l=10, r=90, t=20, b=20),
    )
    st.plotly_chart(fig_cand, use_container_width=True)

    # Summary metrics
    total_c   = cand_df["total_votes"].sum()
    w_row     = cand_df[cand_df["candidate"] == winner_name].iloc[0]
    r_row     = cand_df.sort_values("total_votes", ascending=False).iloc[1]
    margin    = int(w_row["total_votes"]) - int(r_row["total_votes"])

    m1, m2, m3 = st.columns(3)
    m1.metric("🏆 Winner",          w_row["candidate"], w_row["party"])
    m2.metric("📊 Winning Margin",  f"{margin:,} votes", f"{margin/total_c*100:.1f}% of total")
    m3.metric("🗳️ Total Votes",     f"{total_c:,}",      f"{len(cand_df)} candidates")
