# Hotel Revenue Management Dashboard

An interactive dashboard built with **Python, Streamlit and Plotly** to help a hotel revenue manager understand booking cancellations, seasonal pricing and channel risk across a City Hotel and a Resort Hotel.

Built as a group project for **ICT305 Data Visualisation** at Murdoch University.

## Features

- **Linked sidebar filters**: hotel, arrival date range, market segment and lead time. Every KPI and chart updates together.
- **Four tabs**
  - **Overview**: headline KPIs, monthly bookings by outcome, and cancellation rate trends
  - **Explore**: what drives cancellations, a market segment × lead time risk heatmap, and room rate distributions by month
  - **Insights**: four key findings, including the anomaly that non-refundable bookings cancel *more*, not less
  - **Decide**: highest-risk booking profiles and an overbooking planner
- **Accessible design**: the Okabe-Ito colour-blind-safe palette, plus dash styles, marker shapes and hatching, so colour is never the only cue

## Tech stack

Python · pandas · NumPy · Streamlit · Plotly

## Getting started

Requires Python 3.10 or later.

```bash
git clone https://github.com/<your-username>/hotel-revenue-dashboard.git
cd hotel-revenue-dashboard

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run src/app.py
```

The dashboard opens at http://localhost:8501.

To print a summary of the data cleaning steps without starting the dashboard:

```bash
python src/cleaning.py
```

## Project structure

```
data/hotel_bookings.csv   Raw dataset (unchanged)
src/cleaning.py           Data cleaning, validation and feature engineering
src/metrics.py            KPI and chart calculations (pure pandas)
src/app.py                Streamlit dashboard (layout, filters, charts)
.streamlit/config.toml    Theme settings
requirements.txt          Python dependencies
```

## Dataset

Antonio, N., Almeida, A., & Nunes, L. (2019). Hotel booking demand datasets. *Data in Brief*, 22, 41–49. https://doi.org/10.1016/j.dib.2018.11.126
