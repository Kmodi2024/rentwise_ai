# RentWise AI — Week 1 Vibe Coding Project

An interactive rental property analytics dashboard using **fictional** CSV data. Includes property filters, cash flow visualizations, rent payment tracking, maintenance reporting, and explainable rule-based insights.

## Setup

```bash
pip install -r requirements.txt
python generate_data.py
streamlit run app.py
```

## Dataset schema
Properties also include `street_address`, `city`, `state`, `zip_code`, `country`, and
`full_address`. The included street addresses are fictional examples in real Boston
ZIP areas, not verified property locations. Replace them with actual portfolio addresses
before interpreting market comparisons. ZIP codes load as text to retain leading zeros.

Financial Analytics compares current per-unit rents with ZIP-level Zillow ZORI data.
ZORI data automatically loads from `data/Zip_zori_uc_sfrcondomfr_sm_month.csv`
when present; an optional upload overrides it. ISO and spreadsheet-style month
headers are supported. The comparison reports actual coverage per ZIP; the supplied
file ends in August 2026, so September 2026 is not estimated.

Data is published by [Zillow Research](https://www.zillow.com/research/data/). It matches `RegionName` to
property ZIPs and compares current per-unit rent to the mean of available monthly
ZORI values within the shared date filters. ZORI measures typical market rent rather
than a simple average of listings; this is not a comparison matched for bedrooms,
size, or condition. Missing matches remain blank. No portal scraping or live market
data connection is included.

The included sample covers 36 completed months, October 2023 through September 2026,
using October 11, 2026 as the reference date. Running the generator replaces the
fictional CSV datasets. To generate a different rolling three-year sample, run
`python generate_data.py --as-of YYYY-MM-DD`.

The sidebar includes inclusive **Start date** and **End date** controls. Rent records
are filtered by `due_date` (preserving the rent-period accounting basis), while
expenses and maintenance are filtered by `date`. Partial-month selections include
only records whose dates fall within the selection. Occupancy remains a current snapshot.

- `properties.csv`: property_id, property_name, units, monthly_rent_per_unit, occupied_units
- `payments.csv`: payment_id, property_id, unit, month, due_date, amount_due, amount_paid, payment_date, status
- `expenses.csv`: expense_id, property_id, date, category, amount, description
- `maintenance.csv`: request_id, property_id, date, category, priority, status, estimated_cost, actual_cost

## Notes
- Run automated checks with `python -m unittest discover -s tests -v`. Tests cover dashboard views, shared filters, cash flow, weighted occupancy, duplicate expenses, missing data, empty results, and insight thresholds.
- Exact duplicate CSV rows are counted once. Conflicting records sharing an ID are excluded with a warning until the source is corrected; otherwise identical expenses with distinct IDs remain separate transactions. Missing or invalid unit counts make occupancy unavailable rather than implying zero occupancy.
- Financial Analytics includes monthly cash flow, property comparisons, cash flow margins, and expense category totals and shares. Rent Tracking includes monthly and property rent collection rates (collected rent / rent due). All charts use the shared property and inclusive date filters; amounts are USD.
- Missing or invalid numeric values are treated as zero and disclosed in data quality notes. Missing categories are grouped as Unknown; invalid dates are excluded from date-filtered analysis. Missing/empty CSVs produce empty datasets. Rates and margins with zero denominators remain unavailable rather than displaying misleading percentages.
- All records are synthetic; never publish real tenant details or private financial records.
- Cash flow is rent collected minus tracked expenses, not accounting profit or tax liability.
- Occupancy is the current snapshot from properties.csv, not a historical time series.
- AI Insights uses transparent statistical rules rather than an LLM; a future version can add optional AI summaries.
