# V3.3 Calculation and Sheet Mapping Audit

The updated rule workbook defines `quantity_basis`, rather than requiring the app to infer whether a formula's result is a bottle or a case. Purchasing pack factors are derived from `Ingredients.case size` and `Source`. `PO_Alcohol_Matrix.bottles_per_guide_unit` defines the translation from guest-band guide units into individual bottles; the code does not embed wine, beer or spirits multipliers.

For a rule where `quantity_basis=Individual`, individual demand = formula result. For a rule where `quantity_basis=Purchase`, individual demand = formula result × current PACK. Then combine meal/cocktail/alcohol demand in individual units, and place an order for `ceil(combined demand / PACK)` purchase units. A 15-glass rack or 50-glass roll both use their own master case size when Source is Unit.

The Admin **How calculations work** panel now exposes the current formula, quantity basis, Bottle Size, case size, Yield, PO unit and conversion for each water/soft drinks/juice/mixer rule; the alcohol matrix's guide unit, multiplier and all guest band columns; and the garnish/glassware conversion rules. Changes to Google Sheets will be reflected after refresh.

Automated regression suite: see `tests/test_v33.py`. It contains synthetic data fixtures and does **not** establish correctness of business consumption assumptions for an actual event. Verify the live Sheet's prices, pack sizes, alcohol shares, VAT and rule choices before generating supplier orders. Live Google Sheets authentication/write and visual Streamlit behavior were not tested in this environment.
