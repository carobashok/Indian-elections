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
.main-header { font-family:'Playfair Display',serif; font-size:2.4rem; font-weight:900; color:#1a1a2e; line-height:1.1; margin-bottom:0; }
.sub-header  { font-size:0.9rem; color:#6b7280; margin-top:4px; margin-bottom:1.4rem; }
.kpi-card    { background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%); border-radius:12px; padding:1.1rem 1.4rem; color:white; }
.kpi-label   { font-size:0.72rem; text-transform:uppercase; letter-spacing:1.5px; color:#9ca3af; margin-bottom:4px; }
.kpi-value   { font-family:'Playfair Display',serif; font-size:1.9rem; font-weight:700; color:#f59e0b; line-height:1; }
.kpi-sub     { font-size:0.75rem; color:#6b7280; margin-top:4px; }
.section-title { font-family:'Playfair Display',serif; font-size:1.25rem; font-weight:700; color:#1a1a2e;
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
    resp = (
        get_client().table("election_results").select("*")
        .eq("election_year", year).eq("state", state).eq("election", election)
        .execute()
    )
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

    sel_year     = st.selectbox("📅 Election Year", sorted(fdf["election_year"].dropna().unique(), reverse=True))
    sel_state    = st.selectbox("🏛️ State",         sorted(fdf[fdf["election_year"]==sel_year]["state"].unique()))
    sel_election = st.selectbox("🗂️ Election Type", sorted(
        fdf[(fdf["election_year"]==sel_year)&(fdf["state"]==sel_state)]["election"].unique()
    ))
    st.divider()
    st.caption("Refreshes every 5 min · Powered by Supabase")

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
    f'<div class="main-header">🗳️ {sel_state} · {sel_election} · {sel_year}</div>'
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

tab1,tab2,tab3,tab4 = st.tabs(["🏆  Winners Board","🎯  Party Performance","🥧  Vote Share","👤  Candidate Comparison"])

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
# TAB 2 · Party Performance
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
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
with tab3:
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

    st.markdown('<div class="section-title">Constituency-level Vote Share</div>', unsafe_allow_html=True)
    sel_const_vs = st.selectbox("Select Constituency", sorted(df["constituency"].unique()), key="vs_const")
    c_df = df[df["constituency"]==sel_const_vs].sort_values("total_votes", ascending=True).copy()
    c_df["share"]      = (c_df["total_votes"] / c_df["total_votes"].sum() * 100).round(2)
    c_df["cand_label"] = c_df["candidate"].apply(lambda n: shorten(n, 24))
    c_df["pty_short"]  = c_df["party"].apply(lambda p: shorten(p, 26))

    fig_cv = go.Figure()
    colors3 = px.colors.qualitative.Bold
    pty_color = {p: colors3[i%len(colors3)] for i,p in enumerate(c_df["pty_short"].unique())}
    for _, row in c_df.iterrows():
        fig_cv.add_trace(go.Bar(
            x=[row["total_votes"]],
            y=[row["cand_label"]],
            orientation="h",
            marker_color=pty_color.get(row["pty_short"],"#888"),
            text=f'{row["share"]:.1f}%',
            textposition="outside",
            textfont=dict(size=15, color="#1a1a2e"),
            showlegend=False,
            hovertemplate=f"<b>{row['candidate']}</b><br>Party: {row['party']}<br>EVM: {row['evm_votes']:,}<br>Postal: {row['postal_votes']:,}<br>Total: {row['total_votes']:,}<extra></extra>",
        ))
    fig_cv.update_layout(**hbar_layout(len(c_df), left_margin=260, right_margin=100, title_x="Total Votes"))
    st.plotly_chart(fig_cv, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 · Candidate Comparison
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-title">Candidate-wise Results by Constituency</div>', unsafe_allow_html=True)
    sel_const   = st.selectbox("Select Constituency", sorted(df["constituency"].unique()), key="cand_const")
    cand_df     = df[df["constituency"]==sel_const].sort_values("total_votes", ascending=True).copy()
    winner_name = cand_df.iloc[-1]["candidate"]

    fig_cand = go.Figure()
    for _, row in cand_df.iterrows():
        is_w  = row["candidate"] == winner_name
        label = f"{'🏆 ' if is_w else ''}{shorten(row['candidate'],24)}"
        fig_cand.add_trace(go.Bar(
            x=[row["total_votes"]],
            y=[label],
            orientation="h",
            marker_color="#f59e0b" if is_w else "#1a1a2e",
            text=f"{row['total_votes']:,}",
            textposition="outside",
            textfont=dict(size=15, color="#1a1a2e"),
            showlegend=False,
            hovertemplate=(
                f"<b>{row['candidate']}</b><br>Party: {row['party']}<br>"
                f"EVM: {row['evm_votes']:,}<br>Postal: {row['postal_votes']:,}<br>"
                f"Total: {row['total_votes']:,}<extra></extra>"
            ),
        ))
    fig_cand.update_layout(**hbar_layout(len(cand_df), left_margin=260, right_margin=130, title_x="Total Votes"))
    st.plotly_chart(fig_cand, use_container_width=True)

    total_c = cand_df["total_votes"].sum()
    w_row   = cand_df[cand_df["candidate"]==winner_name].iloc[0]
    r_row   = cand_df.sort_values("total_votes", ascending=False).iloc[1]
    margin  = int(w_row["total_votes"]) - int(r_row["total_votes"])

    m1,m2,m3 = st.columns(3)
    m1.metric("🏆 Winner",         w_row["candidate"],  w_row["party"])
    m2.metric("📊 Winning Margin", f"{margin:,} votes", f"{margin/total_c*100:.1f}% of total")
    m3.metric("🗳️ Total Votes",    f"{total_c:,}",      f"{len(cand_df)} candidates")
