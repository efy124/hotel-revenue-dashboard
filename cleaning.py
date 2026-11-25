"""
cleaning.py
-----------
Data cleaning, validation and feature engineering for the Hotel Booking
Demand dataset (Antonio, Almeida & Nunes, 2019, Data in Brief, 22, 41-49).

Every cleaning decision is recorded in CLEANING_LOG so the dashboard and the
report can show exactly what was changed and why (transparency / data
integrity requirement of the brief).

Run directly to print a cleaning summary:
    python src/cleaning.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Path to the raw CSV, resolved relative to this file so the app runs from
# any working directory.
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "hotel_bookings.csv"

# Calendar order for months (the raw file stores month names as text).
MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]

# Lead-time bands used throughout the dashboard. Bands make cancellation
# risk easier to read than a raw continuous scatter of 0-700 days.
LEAD_TIME_BINS = [-1, 7, 30, 90, 180, 365, np.inf]
LEAD_TIME_LABELS = ["0-7 days", "8-30 days", "31-90 days",
                    "91-180 days", "181-365 days", "Over 1 year"]

CLEANING_LOG: list[dict] = []


def _log(step: str, rows_affected: int, reason: str) -> None:
    """Record a cleaning step for display in the dashboard and report."""
    CLEANING_LOG.append(
        {"Step": step, "Rows affected": int(rows_affected), "Reason": reason}
    )


def load_raw(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load the raw CSV without any modification."""
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned copy of the raw bookings data.

    Steps are ordered so that missing values are handled before any
    filtering that depends on them (e.g. total guests uses `children`).
    """
    CLEANING_LOG.clear()
    df = df.copy()

    # 1. Missing values ---------------------------------------------------
    n = df["children"].isna().sum()
    df["children"] = df["children"].fillna(0).astype(int)
    _log("Fill missing children with 0", n,
         "Only 4 rows; booking most likely had no children.")

    n = df["country"].isna().sum()
    df["country"] = df["country"].fillna("Unknown")
    _log("Fill missing country with 'Unknown'", n,
         "Keeps the booking for all non-geographic analysis.")

    # In this dataset an empty agent/company means the booking was NOT made
    # through an agent/company (per the dataset documentation), so the gap
    # is meaningful rather than missing. We convert to a clear flag.
    n = df["agent"].isna().sum()
    df["booked_via_agent"] = df["agent"].notna()
    _log("Convert missing agent to 'no agent' flag", n,
         "Missing agent means no travel agent was used, not unknown data.")

    n = df["company"].isna().sum()
    df["booked_via_company"] = df["company"].notna()
    _log("Convert missing company to 'no company' flag", n,
         "Missing company means not a company booking, not unknown data.")
    df = df.drop(columns=["agent", "company"])  # IDs are anonymised codes

    # 2. Inconsistent categories ------------------------------------------
    n = (df["meal"] == "Undefined").sum()
    df["meal"] = df["meal"].replace("Undefined", "SC")
    _log("Merge meal 'Undefined' into 'SC' (self catering)", n,
         "Dataset documentation states both codes mean no meal package.")

    mask = (df["market_segment"] == "Undefined") | \
           (df["distribution_channel"] == "Undefined")
    n = mask.sum()
    df = df[~mask]
    _log("Drop rows with 'Undefined' segment or channel", n,
         "Too few rows to analyse and cannot be assigned to a category.")

    # 3. Invalid records ---------------------------------------------------
    mask = (df["adults"] + df["children"] + df["babies"]) == 0
    n = mask.sum()
    df = df[~mask]
    _log("Drop bookings with zero guests", n,
         "A room booking with no guests is a data-entry error.")

    mask = df["adr"] < 0
    n = mask.sum()
    df = df[~mask]
    _log("Drop negative ADR", n, "A negative room rate is not valid.")

    mask = df["adr"] > 1000
    n = mask.sum()
    df = df[~mask]
    _log("Drop ADR above 1,000", n,
         "Single extreme value (5,400) about 10x the next highest rate; "
         "treated as an entry error so it does not distort averages.")

    # Note: zero-ADR bookings are KEPT. Most are Complementary or
    # Aviation-crew bookings, which are legitimate business. Revenue KPIs
    # exclude them naturally because they contribute 0 revenue.

    # Note: exact duplicate rows are KEPT. The dataset has no booking ID,
    # so identical rows are indistinguishable from genuine separate
    # bookings (common for group bookings made together). Removing them
    # would undercount group business. This is listed as a limitation.
    _log("Keep exact duplicate rows (no change)", df.duplicated().sum(),
         "No booking ID exists; duplicates are likely genuine group "
         "bookings. Flagged as a limitation in the report.")

    # 4. Feature engineering ----------------------------------------------
    df["arrival_date"] = pd.to_datetime(
        df["arrival_date_year"].astype(str) + "-"
        + df["arrival_date_month"] + "-"
        + df["arrival_date_day_of_month"].astype(str),
        format="%Y-%B-%d",
    )
    df["arrival_month_start"] = df["arrival_date"].dt.to_period("M").dt.to_timestamp()
    df["arrival_month"] = pd.Categorical(
        df["arrival_date_month"], categories=MONTH_ORDER, ordered=True
    )

    df["total_nights"] = df["stays_in_weekend_nights"] + df["stays_in_week_nights"]
    df["total_guests"] = df["adults"] + df["children"] + df["babies"]

    # Revenue only counts if the booking was not cancelled.
    df["booking_value"] = df["adr"] * df["total_nights"]
    df["realised_revenue"] = np.where(df["is_canceled"] == 1, 0.0, df["booking_value"])

    df["lead_time_band"] = pd.cut(
        df["lead_time"], bins=LEAD_TIME_BINS, labels=LEAD_TIME_LABELS
    )
    df["room_changed"] = df["reserved_room_type"] != df["assigned_room_type"]
    df["guest_type"] = np.where(df["is_repeated_guest"] == 1, "Repeat", "First-time")

    # reservation_status / reservation_status_date describe the outcome of
    # the booking (they leak the cancellation result), so they are dropped
    # to prevent them being used to "explain" cancellations.
    df = df.drop(columns=["reservation_status", "reservation_status_date"])

    return df.reset_index(drop=True)


def load_clean(path: Path = DATA_PATH) -> pd.DataFrame:
    """Convenience wrapper: load the raw file and return cleaned data."""
    return clean(load_raw(path))


if __name__ == "__main__":
    raw = load_raw()
    cleaned = clean(raw)
    print(f"Raw rows:     {len(raw):,}")
    print(f"Cleaned rows: {len(cleaned):,}")
    print(f"Date range:   {cleaned['arrival_date'].min():%d %b %Y} "
          f"to {cleaned['arrival_date'].max():%d %b %Y}\n")
    print(pd.DataFrame(CLEANING_LOG).to_string(index=False))
