"""
metrics.py
----------
All calculations used by the dashboard. Keeping these separate from the
Streamlit UI (app.py) means:
  * every chart and KPI is computed from the SAME filtered DataFrame,
    which guarantees consistent filtering logic across the dashboard;
  * the logic can be tested without running the dashboard.
"""

import pandas as pd

# Minimum number of bookings before a rate is shown. Rates from tiny
# groups are unreliable and could mislead (honesty / data integrity).
MIN_GROUP_SIZE = 30


def apply_filters(df: pd.DataFrame, hotels, start, end, segments,
                  lead_range) -> pd.DataFrame:
    """Apply every sidebar filter in one place and return the subset.

    All dashboard sections use the output of this function, so a change
    to any filter updates every KPI and chart together.
    """
    mask = (
        df["hotel"].isin(hotels)
        & df["arrival_date"].between(pd.Timestamp(start), pd.Timestamp(end))
        & df["market_segment"].isin(segments)
        & df["lead_time"].between(lead_range[0], lead_range[1])
    )
    return df[mask]


def kpis(df: pd.DataFrame) -> dict:
    """Headline indicators for the Overview section."""
    if df.empty:
        return {}
    stayed = df[df["is_canceled"] == 0]
    return {
        "bookings": len(df),
        "cancel_rate": df["is_canceled"].mean(),
        # ADR is averaged over bookings that actually stayed, because
        # cancelled bookings never generated that rate.
        "adr": stayed["adr"].mean() if not stayed.empty else 0.0,
        "revenue": df["realised_revenue"].sum(),
        "lost_value": df.loc[df["is_canceled"] == 1, "booking_value"].sum(),
        "lead_time": df["lead_time"].median(),
    }


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Bookings, cancellations and cancellation rate per month and hotel."""
    out = (
        df.groupby(["arrival_month_start", "hotel"])
        .agg(bookings=("is_canceled", "size"),
             cancellations=("is_canceled", "sum"))
        .reset_index()
    )
    out["stayed"] = out["bookings"] - out["cancellations"]
    out["cancel_rate"] = out["cancellations"] / out["bookings"]
    return out


def cancel_rate_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Cancellation rate for each category of `column`, split by hotel.

    Groups smaller than MIN_GROUP_SIZE are removed so tiny samples are
    not presented as reliable rates.
    """
    out = (
        df.groupby([column, "hotel"], observed=True)
        .agg(bookings=("is_canceled", "size"),
             cancel_rate=("is_canceled", "mean"))
        .reset_index()
    )
    return out[out["bookings"] >= MIN_GROUP_SIZE]


def risk_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Cancellation rate for every lead-time band x market segment pair.

    Returns a wide table (rows = segment, columns = lead-time band).
    Cells with fewer than MIN_GROUP_SIZE bookings are left blank.
    """
    grp = (
        df.groupby(["market_segment", "lead_time_band"], observed=True)
        ["is_canceled"].agg(["mean", "size"])
    )
    grp.loc[grp["size"] < MIN_GROUP_SIZE, "mean"] = float("nan")
    return grp["mean"].unstack("lead_time_band")


def adr_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Mean ADR per calendar month and hotel, for stays (not cancellations)."""
    stayed = df[(df["is_canceled"] == 0) & (df["adr"] > 0)]
    return (
        stayed.groupby(["arrival_month", "hotel"], observed=True)["adr"]
        .agg(["mean", "size"])
        .reset_index()
        .rename(columns={"mean": "adr", "size": "stays"})
    )


def high_risk_profiles(df: pd.DataFrame, min_n: int = 100, top: int = 5,
                       exclude_non_refund: bool = True) -> pd.DataFrame:
    """Booking profiles (segment + lead-time band + deposit type) with the
    highest cancellation rates, ignoring groups under `min_n` bookings.

    Non-refundable bookings are excluded by default because their ~99%
    cancellation rate is a suspected recording anomaly (see Insights tab)
    and would otherwise fill the whole table.
    """
    if exclude_non_refund:
        df = df[df["deposit_type"] != "Non Refund"]
    keys = ["market_segment", "lead_time_band", "deposit_type"]
    out = (
        df.assign(lost_value=df["booking_value"] * df["is_canceled"])
        .groupby(keys, observed=True)
        .agg(bookings=("is_canceled", "size"),
             cancel_rate=("is_canceled", "mean"),
             lost_value=("lost_value", "sum"))
        .reset_index()
    )
    out = out[out["bookings"] >= min_n]
    return out.sort_values("cancel_rate", ascending=False).head(top)


def overbooking_estimate(df: pd.DataFrame, hotel: str, month: str,
                         rooms: int, cover_share: float) -> dict | None:
    """Rough overbooking buffer for one hotel and calendar month.

    expected_cancellations = rooms x historical cancellation rate
    suggested_buffer      = expected_cancellations x cover_share

    `cover_share` (0-1) lets the manager choose how much of the expected
    cancellations to cover: lower = safer (fewer walked guests),
    higher = more aggressive (fewer empty rooms).
    """
    sub = df[(df["hotel"] == hotel) & (df["arrival_date_month"] == month)]
    if len(sub) < MIN_GROUP_SIZE:
        return None
    rate = sub["is_canceled"].mean()
    expected = rooms * rate
    return {
        "bookings": len(sub),
        "cancel_rate": rate,
        "expected_cancellations": expected,
        "suggested_buffer": int(expected * cover_share),
    }
