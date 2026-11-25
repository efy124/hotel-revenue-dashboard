"""
app.py
------
Hotel Booking Demand: Revenue Management Dashboard (ICT305 Group Project)

Stakeholder:    Hotel Revenue Manager (covering City Hotel and Resort Hotel)
Decision level: Tactical (monthly / seasonal policy, pricing and channel decisions)

Run from the project root (the folder containing README.md):
    streamlit run src/app.py

Structure
    Sidebar filters -> apply_filters() -> ONE filtered DataFrame (`fdf`)
    `fdf` feeds every KPI and chart in all four tabs, so every view is
    linked and filters behave consistently everywhere.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from cleaning import CLEANING_LOG, LEAD_TIME_LABELS, MONTH_ORDER, load_clean
import metrics as m

# ---------------------------------------------------------------------------
# Page setup and shared visual settings
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Hotel Revenue Dashboard", layout="wide")

# Okabe-Ito colour-blind-safe palette. Each hotel keeps the same colour AND
# the same legend order in every chart (consistency).
HOTEL_ORDER = ["City Hotel", "Resort Hotel"]
HOTEL_COLOURS = {"City Hotel": "#0072B2", "Resort Hotel": "#E69F00"}
OUTCOME_COLOURS = {"Stayed": "#009E73", "Cancelled": "#D55E00"}

# Colour is never the only cue (accessibility for colour-blind viewers).
# Resort Hotel lines are dashed with diamond markers; Resort Hotel and
# "Cancelled" bars carry diagonal hatching, so every series can be told
# apart in greyscale or with any type of colour blindness.
HOTEL_DASH = {"City Hotel": "solid", "Resort Hotel": "dash"}
HOTEL_SYMBOL = {"City Hotel": "circle", "Resort Hotel": "diamond"}
HOTEL_PATTERN = {"City Hotel": "", "Resort Hotel": "/"}
PATTERN_STYLE = dict(marker_pattern_fillmode="overlay",
                     marker_pattern_fgcolor="white",
                     marker_pattern_fgopacity=0.55,
                     marker_pattern_size=8)
TEMPLATE = "plotly_white"


def show(fig, height: int = 400) -> None:
    """Apply shared layout settings and render a Plotly figure.

    Every chart goes through this function so fonts, margins and legend
    placement are identical across the dashboard.
    """
    fig.update_layout(
        template=TEMPLATE, height=height,
        margin=dict(l=10, r=10, t=90, b=10),
        legend_title_text="",
        # Horizontal legend above the plot, right-aligned: always visible,
        # never overlaps the title, same place on every chart.
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, traceorder="normal"),
        hoverlabel=dict(font_size=14),
        font=dict(size=14),
    )
    st.plotly_chart(fig, use_container_width=True)


def pct(x: float) -> str:
    return f"{x:.1%}"


# ---------------------------------------------------------------------------
# Data loading (cached so cleaning runs once, not on every interaction)
# ---------------------------------------------------------------------------
@st.cache_data
def get_data():
    df = load_clean()
    # Copy the log because CLEANING_LOG is cleared on each clean() call.
    return df, pd.DataFrame(CLEANING_LOG)


df, cleaning_log = get_data()
baseline = m.kpis(df)  # whole-dataset KPIs, used as the comparison point

ALL_SEGMENTS = sorted(df["market_segment"].unique())
MIN_DATE = df["arrival_date"].min().date()
MAX_DATE = df["arrival_date"].max().date()
MAX_LEAD = int(df["lead_time"].max())

# Default value of every filter, stored in session state so a single
# "Reset" button can restore them all.
FILTER_DEFAULTS = {
    "f_hotel": "Both hotels",
    "f_dates": (MIN_DATE, MAX_DATE),
    "f_segments": ALL_SEGMENTS,
    "f_lead": (0, MAX_LEAD),
}
for key, value in FILTER_DEFAULTS.items():
    st.session_state.setdefault(key, value)


def reset_filters() -> None:
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# Sidebar: the four global filters (applied to every section)
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")
st.sidebar.caption("These filters apply to every section of the dashboard.")

# A radio button replaces the multiselect: with only two hotels it is one
# click instead of removing tags, and all options are always visible.
hotel_choice = st.sidebar.radio(
    "Hotel", ["Both hotels", "City Hotel", "Resort Hotel"], key="f_hotel",
    help="Compare the two properties or focus on one.",
)
hotels = HOTEL_ORDER if hotel_choice == "Both hotels" else [hotel_choice]

date_range = st.sidebar.date_input(
    "Arrival date range", key="f_dates",
    min_value=MIN_DATE, max_value=MAX_DATE, format="DD/MM/YYYY",
    help="Focus on a season or period. Data covers July 2015 to August 2017.",
)
# While the user is mid-selection the widget returns only a start date.
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start, end = date_range
else:
    start = date_range[0] if isinstance(date_range, (tuple, list)) and date_range else MIN_DATE
    end = MAX_DATE
    st.sidebar.info("Select an end date to finish the range. "
                    "Showing data from the start date onwards.")

segments = st.sidebar.multiselect(
    "Market segment", ALL_SEGMENTS, key="f_segments",
    placeholder="Choose one or more segments",
    help="Isolate the customer groups a policy would apply to.",
)

lead_range = st.sidebar.slider(
    "Lead time (days between booking and arrival)",
    min_value=0, max_value=MAX_LEAD, key="f_lead",
    help="Lead time is the strongest driver of cancellation risk.",
)

st.sidebar.button("Reset all filters", on_click=reset_filters,
                  use_container_width=True)

fdf = m.apply_filters(df, hotels, start, end, segments, lead_range)
st.sidebar.markdown(f"**{len(fdf):,}** of {len(df):,} bookings selected")

# ---------------------------------------------------------------------------
# Header, with a plain-language summary of the active filters so the user
# always knows what the numbers on every tab refer to.
# ---------------------------------------------------------------------------
st.title("Hotel Revenue Management Dashboard")
st.markdown(
    "Supports the revenue manager's tactical decisions on **cancellation "
    "policy**, **seasonal pricing**, **channel mix** and **overbooking** "
    "for the City Hotel and Resort Hotel."
)

seg_text = ("all market segments" if len(segments) == len(ALL_SEGMENTS)
            else f"{len(segments)} of {len(ALL_SEGMENTS)} market segments")
st.info(
    f"**Showing:** {hotel_choice.lower() if hotel_choice == 'Both hotels' else hotel_choice} · "
    f"arrivals {pd.Timestamp(start):%d %b %Y} to {pd.Timestamp(end):%d %b %Y} · "
    f"{seg_text} · lead time {lead_range[0]}–{lead_range[1]} days · "
    f"**{len(fdf):,} bookings**"
)

if fdf.empty:
    st.warning("No bookings match these filters. Add a market segment, widen "
               "the date or lead-time range, or press **Reset all filters**.")
    st.stop()

is_filtered = len(fdf) != len(df)

tab_overview, tab_explore, tab_insights, tab_decide = st.tabs(
    ["Overview", "Exploratory analysis", "Insight highlights", "Decision support"]
)

# ===========================================================================
# 1. OVERVIEW / EXECUTIVE SUMMARY
# ===========================================================================
with tab_overview:
    k = m.kpis(fdf)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bookings", f"{k['bookings']:,}",
              help="Number of bookings matching the current filters.")
    # When filtered, show how the selection compares with all bookings.
    # "inverse" colours a higher cancellation rate red (bad) and lower green.
    c2.metric("Cancellation rate", pct(k["cancel_rate"]),
              delta=(f"{(k['cancel_rate'] - baseline['cancel_rate']) * 100:+.1f} pts vs all"
                     if is_filtered else None),
              delta_color="inverse",
              help="Share of bookings that were cancelled.")
    c3.metric("Average daily rate (stays)", f"€{k['adr']:,.2f}",
              delta=(f"€{k['adr'] - baseline['adr']:+.2f} vs all" if is_filtered else None),
              help="Average nightly room rate of bookings that were not cancelled.")
    c4.metric("Realised room revenue", f"€{k['revenue'] / 1e6:,.2f}M",
              help="Room revenue from bookings that were not cancelled.")
    c5.metric("Value of cancelled bookings", f"€{k['lost_value'] / 1e6:,.2f}M",
              help="Room revenue the cancelled bookings would have generated.")

    monthly = m.monthly_summary(fdf)
    left, right = st.columns(2)

    with left:
        # Stacked bars: full height = total demand, top part = demand lost.
        # Built with graph_objects rather than plotly express: newer Plotly
        # versions give each px colour group its own "offsetgroup", which
        # places the bars side by side even when barmode is "stack".
        totals = (monthly.groupby("arrival_month_start")[["stayed", "cancellations"]]
                  .sum().reset_index())
        fig = go.Figure([
            go.Bar(x=totals["arrival_month_start"], y=totals["stayed"],
                   name="Stayed", marker_color=OUTCOME_COLOURS["Stayed"],
                   hovertemplate="%{x|%b %Y}<br>%{y:,} stayed<extra></extra>"),
            go.Bar(x=totals["arrival_month_start"], y=totals["cancellations"],
                   name="Cancelled", marker_color=OUTCOME_COLOURS["Cancelled"],
                   marker_pattern_shape="/",
                   hovertemplate="%{x|%b %Y}<br>%{y:,} cancelled<extra></extra>"),
        ])
        fig.update_traces(**PATTERN_STYLE)
        fig.update_layout(barmode="stack", title="Monthly bookings by outcome",
                          xaxis_title="Arrival month", yaxis_title="Bookings")
        show(fig)
        # (Legend order is fixed inside show(): stacked charts otherwise list
        # the top segment first, i.e. "Cancelled" before "Stayed".)

    with right:
        fig = px.line(monthly, x="arrival_month_start", y="cancel_rate", color="hotel",
                      line_dash="hotel", symbol="hotel",
                      line_dash_map=HOTEL_DASH, symbol_map=HOTEL_SYMBOL,
                      markers=True, color_discrete_map=HOTEL_COLOURS,
                      category_orders={"hotel": HOTEL_ORDER},
                      title="Monthly cancellation rate by hotel",
                      labels={"arrival_month_start": "Arrival month",
                              "cancel_rate": "Cancellation rate"})
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        fig.update_traces(hovertemplate="%{x|%b %Y}<br>%{y:.1%} cancelled")
        show(fig)

    st.caption("July 2015 and August 2017 are the first and last months of "
               "the data. 2015 and 2017 are partial years, so compare months "
               "or seasons rather than annual totals.")

    with st.expander("About the data and how it was cleaned"):
        st.markdown(
            "Source: Antonio, Almeida & Nunes (2019), *Hotel booking demand "
            "datasets*, Data in Brief 22, 41-49. Real bookings from two "
            "hotels in Portugal, arrivals July 2015 to August 2017."
        )
        st.dataframe(cleaning_log, hide_index=True, use_container_width=True)

# ===========================================================================
# 2. EXPLORATORY ANALYSIS
# ===========================================================================
with tab_explore:
    st.subheader("What drives cancellations?")
    dims = {
        "Market segment": "market_segment",
        "Distribution channel": "distribution_channel",
        "Deposit type": "deposit_type",
        "Customer type": "customer_type",
        "Lead time band": "lead_time_band",
        "Guest type (first-time vs repeat)": "guest_type",
    }
    dim_label = st.selectbox("Compare cancellation rate by", list(dims))
    col = dims[dim_label]

    by_dim = m.cancel_rate_by(fdf, col)
    if by_dim.empty:
        st.info("Not enough bookings in any group to show reliable rates.")
    else:
        # Plotly draws the first category at the top. Lead time keeps its
        # natural order; other categories put the highest rate at the top.
        order = (LEAD_TIME_LABELS if col == "lead_time_band" else
                 by_dim.groupby(col)["cancel_rate"].mean()
                 .sort_values(ascending=False).index.tolist())
        fig = px.bar(by_dim, x="cancel_rate", y=col, color="hotel",
                     pattern_shape="hotel", pattern_shape_map=HOTEL_PATTERN,
                     barmode="group", orientation="h",
                     color_discrete_map=HOTEL_COLOURS,
                     category_orders={col: order, "hotel": HOTEL_ORDER},
                     custom_data=["hotel", "bookings"],
                     title=f"Cancellation rate by {dim_label.lower()}",
                     labels={"cancel_rate": "Cancellation rate", col: ""})
        fig.update_traces(hovertemplate="%{customdata[0]} · %{y}<br>"
                                        "%{x:.1%} cancelled<br>"
                                        "%{customdata[1]:,} bookings<extra></extra>",
                          **PATTERN_STYLE)
        fig.update_xaxes(tickformat=".0%", range=[0, 1])
        show(fig, height=max(400, 70 * by_dim[col].nunique() + 150))
        st.caption(f"Highest cancellation rate at the top. Groups with fewer "
                   f"than {m.MIN_GROUP_SIZE} bookings are hidden because their "
                   "rates are unreliable.")
        # Text alternative to the chart, for screen readers and exact values.
        with st.expander("View the numbers behind this chart"):
            st.dataframe(
                by_dim.rename(columns={col: dim_label, "hotel": "Hotel",
                                       "bookings": "Bookings",
                                       "cancel_rate": "Cancellation rate"})
                .style.format({"Cancellation rate": "{:.1%}", "Bookings": "{:,}"}),
                hide_index=True, use_container_width=True)

    st.subheader("Where is cancellation risk concentrated?")
    matrix = m.risk_matrix(fdf)
    if matrix.empty:
        st.info("Not enough bookings to build the risk matrix.")
    else:
        matrix.columns = matrix.columns.astype(str)
        fig = px.imshow(matrix, aspect="auto",
                        color_continuous_scale="Oranges", zmin=0, zmax=1,
                        title="Cancellation rate: market segment × lead time",
                        labels={"x": "Lead time band", "y": "Market segment",
                                "color": "Cancellation rate"})
        # Write cell labels manually so blank (unreliable) cells show nothing.
        cell_text = matrix.apply(
            lambda c: c.map(lambda v: "" if pd.isna(v) else f"{v:.0%}"))
        fig.update_traces(text=cell_text.values, texttemplate="%{text}",
                          hovertemplate="%{y} · %{x}<br>%{z:.1%} cancelled"
                                        "<extra></extra>")
        fig.update_coloraxes(colorbar_tickformat=".0%")
        # No gridlines, so blank cells read as intentionally empty.
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=False)
        show(fig, height=460)
        st.caption("Darker cells are booking profiles that cancel most often. "
                   f"Blank cells have fewer than {m.MIN_GROUP_SIZE} bookings, "
                   "too few to estimate a rate.")
        with st.expander("View the numbers behind this chart"):
            st.dataframe(matrix.style.format("{:.1%}", na_rep="–"),
                         use_container_width=True)

    st.subheader("How do room rates vary through the year?")
    stays = fdf[(fdf["is_canceled"] == 0) & (fdf["adr"] > 0)]
    if stays.empty:
        st.info("No completed stays in the current selection.")
    else:
        fig = px.box(stays, x="arrival_month", y="adr", color="hotel",
                     color_discrete_map=HOTEL_COLOURS,
                     category_orders={"arrival_month": MONTH_ORDER,
                                      "hotel": HOTEL_ORDER},
                     title="Distribution of daily rate by arrival month (completed stays)",
                     labels={"arrival_month": "", "adr": "Average daily rate (€)"})
        show(fig, height=460)
        st.caption("City Hotel is always the left box in each month and "
                   "Resort Hotel the right. "
                   "The line in each box is the typical (median) rate; boxes "
                   "show the middle 50% of rates; dots beyond the whiskers are "
                   "unusually high or low rates worth checking.")

# ===========================================================================
# 3. INSIGHT HIGHLIGHTS (annotated, recalculated from the current filters)
# ===========================================================================
with tab_insights:
    st.markdown("Each finding below is recalculated from the current filters, "
                "so the numbers stay accurate as you change the selection.")

    # ---- Insight 1: lead time ------------------------------------------
    st.subheader("1. The further ahead a booking is made, the more likely it is to cancel")
    lt = (fdf.groupby("lead_time_band", observed=True)["is_canceled"]
          .agg(["mean", "size"]).reset_index())
    lt = lt[lt["size"] >= m.MIN_GROUP_SIZE]
    if len(lt) >= 2:
        first, last = lt.iloc[0], lt.iloc[-1]
        fig = px.bar(lt, x="lead_time_band", y="mean",
                     labels={"lead_time_band": "Lead time", "mean": "Cancellation rate"},
                     title="Cancellation rate by lead time")
        fig.update_traces(marker_color="#0072B2",
                          hovertemplate="%{x}<br>%{y:.1%} cancelled<extra></extra>")
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        for row in (first, last):
            fig.add_annotation(x=str(row["lead_time_band"]), y=row["mean"],
                               text=f"{pct(row['mean'])} cancel", showarrow=True,
                               arrowhead=2, ay=-40, font=dict(size=14))
        show(fig)
        ratio = last["mean"] / first["mean"] if first["mean"] > 0 else float("nan")
        st.markdown(
            f"**Finding:** bookings made {last['lead_time_band']} ahead cancel at "
            f"{pct(last['mean'])}, about {ratio:.1f}x the rate of bookings made "
            f"{first['lead_time_band']} ahead ({pct(first['mean'])}).  \n"
            "**What it means:** long-lead bookings are the main source of "
            "cancellation risk, so deposit or cancellation-term changes are "
            "best targeted at them rather than applied to every booking."
        )
    else:
        st.info("Select a wider lead-time range to see this comparison.")

    st.divider()

    # ---- Insight 2: seasonality ----------------------------------------
    st.subheader("2. The two hotels have very different seasonal pricing patterns")
    adr_m = m.adr_by_month(fdf)
    adr_m = adr_m[adr_m["stays"] >= m.MIN_GROUP_SIZE]
    if not adr_m.empty:
        fig = px.line(adr_m, x="arrival_month", y="adr", color="hotel", markers=True,
                      line_dash="hotel", symbol="hotel",
                      line_dash_map=HOTEL_DASH, symbol_map=HOTEL_SYMBOL,
                      color_discrete_map=HOTEL_COLOURS,
                      category_orders={"arrival_month": MONTH_ORDER,
                                       "hotel": HOTEL_ORDER},
                      title="Average daily rate by arrival month (completed stays)",
                      labels={"arrival_month": "", "adr": "Average daily rate (€)"})
        fig.update_traces(hovertemplate="%{x}<br>€%{y:.2f}")
        notes = []
        for hotel, grp in adr_m.groupby("hotel"):
            peak, low = grp.loc[grp["adr"].idxmax()], grp.loc[grp["adr"].idxmin()]
            fig.add_annotation(x=str(peak["arrival_month"]), y=peak["adr"],
                               text=f"{hotel} peak: €{peak['adr']:.0f}",
                               showarrow=True, arrowhead=2, ay=-35,
                               font=dict(size=14))
            notes.append(f"{hotel} peaks in {peak['arrival_month']} "
                         f"(€{peak['adr']:.0f}) and is lowest in "
                         f"{low['arrival_month']} (€{low['adr']:.0f}), "
                         f"a {peak['adr'] / low['adr']:.1f}x swing")
        show(fig)
        st.markdown(
            "**Finding:** " + "; ".join(notes) + ".  \n"
            "**What it means:** pricing and promotions should be planned per "
            "hotel. A single seasonal pricing calendar would underprice one "
            "property's peak or overprice the other's off-season."
        )
    else:
        st.info("Not enough completed stays to compare monthly rates.")

    st.divider()

    # ---- Insight 3: anomaly --------------------------------------------
    st.subheader("3. Anomaly: non-refundable bookings cancel more, not less")
    dep = (fdf.groupby("deposit_type")["is_canceled"]
           .agg(cancel_rate="mean", bookings="size").reset_index())
    dep = dep[dep["bookings"] >= m.MIN_GROUP_SIZE]
    if "Non Refund" in dep["deposit_type"].values and len(dep) >= 2:
        nr = dep.loc[dep["deposit_type"] == "Non Refund", "cancel_rate"].iloc[0]
        fig = px.bar(dep, x="deposit_type", y="cancel_rate",
                     labels={"deposit_type": "Deposit type", "cancel_rate": "Cancellation rate"},
                     title="Cancellation rate by deposit type")
        fig.update_traces(marker_color="#D55E00",
                          hovertemplate="%{x}<br>%{y:.1%} cancelled<extra></extra>")
        fig.update_yaxes(tickformat=".0%", range=[0, 1.1])
        fig.add_annotation(x="Non Refund", y=nr,
                           text="Unexpected: should be the lowest",
                           showarrow=True, arrowhead=2, ay=-30, font=dict(size=14))
        show(fig)
        st.markdown(
            f"**Finding:** non-refundable bookings show a {pct(nr)} cancellation "
            "rate, the opposite of what a non-refundable policy should produce.  \n"
            "**What it means:** this is very likely a recording issue (for "
            "example, bookings flagged as cancelled after a forfeited deposit, "
            "or group blocks released in bulk). It should be checked with the "
            "reservations team before it is used to judge whether deposits work."
        )
    else:
        st.info("Include non-refundable bookings in the selection to see this check.")

    st.divider()

    # ---- Insight 4: loyalty --------------------------------------------
    st.subheader("4. Repeat guests are far more reliable")
    gt = fdf.groupby("guest_type")["is_canceled"].agg(["mean", "size"])
    if ({"Repeat", "First-time"}.issubset(gt.index)
            and gt.loc["Repeat", "size"] >= m.MIN_GROUP_SIZE):
        c1, c2, c3 = st.columns(3)
        c1.metric("First-time guest cancellation rate", pct(gt.loc["First-time", "mean"]))
        c2.metric("Repeat guest cancellation rate", pct(gt.loc["Repeat", "mean"]))
        c3.metric("Share of bookings from repeat guests",
                  pct(gt.loc["Repeat", "size"] / gt["size"].sum()))
        st.markdown(
            "**Finding:** repeat guests cancel much less often, yet make up a "
            "small share of bookings.  \n"
            "**What it means:** growing repeat business (loyalty offers, "
            "direct-booking incentives) would lower cancellation risk as well "
            "as commission costs."
        )
    else:
        st.info("Not enough repeat-guest bookings in this selection.")

# ===========================================================================
# 4. DECISION SUPPORT
# ===========================================================================
with tab_decide:
    st.subheader("How to use this dashboard")
    st.markdown(
        "1. Choose the **hotel** and **arrival date range** for the property "
        "and season you are planning.\n"
        "2. Check the **Overview** for the cancellation rate and value at "
        "risk. When filtered, the KPIs show how your selection compares with "
        "all bookings.\n"
        "3. Use **Exploratory analysis** to find which segments, channels and "
        "lead times drive cancellations. Narrow the **market segment** and "
        "**lead time** filters to test a specific booking profile.\n"
        "4. Use the tools below to turn what you found into a policy or "
        "overbooking decision. **Reset all filters** in the sidebar returns "
        "to the full dataset."
    )

    st.subheader("Decisions this dashboard supports")
    # A Markdown table renders full-contrast, wrapped text (st.table dims
    # the first column, which hurt readability).
    st.markdown(
        "| Decision | Where to look | Possible action |\n"
        "| --- | --- | --- |\n"
        "| Which bookings should require a deposit or stricter cancellation terms? "
        "| Risk matrix, lead-time insight, high-risk profiles below "
        "| Introduce deposits for long-lead, high-risk profiles only |\n"
        "| How should room rates and promotions change across the year? "
        "| Monthly rate box plot, seasonal pricing insight "
        "| Set separate seasonal rate calendars for each hotel |\n"
        "| Which channels and segments should we prioritise? "
        "| Cancellation by segment or channel, repeat-guest insight "
        "| Shift marketing towards direct and repeat guests |\n"
        "| How many extra rooms can we safely sell (overbook) each month? "
        "| Monthly cancellation rate, overbooking planner below "
        "| Overbook by a share of expected cancellations, by month |"
    )

    st.subheader("Highest-risk booking profiles")
    excl = st.checkbox("Exclude non-refundable bookings (suspected data anomaly)",
                       value=True,
                       help="Their ~99% cancellation rate is likely a recording "
                            "issue and would otherwise fill the whole table.")
    risky = m.high_risk_profiles(fdf, exclude_non_refund=excl)
    if risky.empty:
        st.info("No booking profile has at least 100 bookings in this selection.")
    else:
        st.dataframe(
            risky.rename(columns={
                "market_segment": "Market segment", "lead_time_band": "Lead time",
                "deposit_type": "Deposit", "bookings": "Bookings",
                "cancel_rate": "Cancellation rate", "lost_value": "Cancelled value (€)",
            }).style.format({"Cancellation rate": "{:.1%}",
                             "Cancelled value (€)": "€{:,.0f}",
                             "Bookings": "{:,}"}),
            hide_index=True, use_container_width=True,
        )
        st.caption("Profiles with at least 100 bookings, ranked by cancellation "
                   "rate. These are the strongest candidates for a deposit "
                   "requirement or tighter cancellation terms.")

    st.subheader("Overbooking planner")
    st.markdown("Estimate how many extra rooms to sell for a month, based on "
                "that month's historical cancellation rate for the selected "
                "bookings.")
    p1, p2, p3, p4 = st.columns(4)
    plan_hotel = p1.selectbox("Hotel", [h for h in HOTEL_ORDER if h in hotels],
                              key="plan_hotel")
    plan_month = p2.selectbox("Month", MONTH_ORDER, index=7, key="plan_month")
    rooms = p3.number_input("Rooms to sell", min_value=1, value=200, step=10,
                            key="plan_rooms")
    cover_pct = p4.slider("Share of expected cancellations to cover",
                          0, 100, 50, 5, format="%d%%", key="plan_cover",
                          help="Lower is safer (fewer guests turned away); "
                               "higher fills more rooms but risks overbooking.")
    est = m.overbooking_estimate(fdf, plan_hotel, plan_month, rooms, cover_pct / 100)
    if est is None:
        st.info("Not enough bookings for that hotel and month in the current "
                "filters. Widen the date range or segment filter.")
    else:
        e1, e2, e3 = st.columns(3)
        e1.metric("Historical cancellation rate", pct(est["cancel_rate"]))
        e2.metric("Expected cancellations", f"{est['expected_cancellations']:.0f} rooms")
        e3.metric("Suggested overbooking buffer", f"{est['suggested_buffer']} rooms")
        st.caption(
            f"Calculation: {rooms} rooms × {pct(est['cancel_rate'])} cancellation "
            f"rate = {est['expected_cancellations']:.0f} expected cancellations; "
            f"covering {cover_pct}% gives {est['suggested_buffer']} extra rooms. "
            f"Based on {est['bookings']:,} past bookings. This is a planning "
            "guide, not a forecast: it assumes future cancellation behaviour "
            "resembles 2015-2017."
        )

    with st.expander("Limitations to keep in mind"):
        st.markdown(
            "- Data covers 2015-2017 and predates COVID-19, so use it for "
            "patterns and policy logic rather than current demand levels.\n"
            "- Two hotels in Portugal only; findings may not transfer to other markets.\n"
            "- No booking ID, so identical rows cannot be told apart from "
            "genuine repeat bookings (kept, see cleaning log).\n"
            "- Rates are assumed to be in euros; the source does not state the currency.\n"
            "- The non-refundable cancellation pattern is a suspected recording anomaly."
        )
