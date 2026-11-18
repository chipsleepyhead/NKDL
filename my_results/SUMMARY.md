# NYC Taxi — real-data benchmark

Source: `nyc_taxi_demo.duckdb`

- Window: 2025-01-01 00:00:00 -> 2026-08-31 23:00:00
- Zone-hour coverage: 60.8%
- ML1 selected: **Stacking_Ridge**
- Final TEST MAE: **5.8298**
- Final TEST RMSE: **13.0286**
- ML2: **KMeans**

Warning: This is one-hour-ahead backtesting with past observed trip counts available. If deployment forecasts 24 hours in advance, features and validation need redesign. Missing zone-hours are unknown unless zero_fill_confirmed=True after audit.
