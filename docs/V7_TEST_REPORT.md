# Mobile Desk 1.7 test report

Baseline 1.6.0 at `aeb8618` ran on an isolated test database. All 156 baseline tests passed in 198.82 seconds. The baseline Windows 1.6.0 executable completed the synthetic sales, purchase, arrival, return, refund, backup and restore diagnostic flows. No live shop data was opened.

## Measured performance

Windows, Intel Core i5-4310M at 2.70 GHz, Python 3.12, synthetic local SQLite with 5,000 products, 25,000 invoices, 5,000 lots and 30,000 stock movements. Baseline figures are single observations. Version 1.7 query figures are medians of five samples. Startup, first Stock navigation and the write are single observations. The startup figure begins after Qt initialization with an existing shop and excludes first-run catalogue import.

| Operation | 1.6.0 baseline | 1.7.0 |
|---|---:|---:|
| 100 sale records | 49.02 ms | 29.69 ms |
| 100 stock records | 102.58 ms | 9.93 ms |
| Dashboard snapshot | 819.40 ms | 186.03 ms |
| Five-year product report | 492.95 ms | 161.96 ms |
| 25,000-line customer statement read | 447.20 ms | 216.36 ms |
| Product lookup | — | 13.21 ms |
| One-month model report | — | 51.81 ms |
| Routine FIFO sale save | — | 32.96 ms |
| Existing shop to dashboard | — | 330.49 ms |
| First Stock navigation | — | 39.08 ms |

Use `.venv\Scripts\python.exe tools\benchmark_business.py` to repeat the synthetic benchmark. Large statements and selected reports still read synchronously. Stock is paged in SQLite and other report tables render one page at a time. The old Stock plan materialized the lot view before limiting rows and scanned all products and lots. Stock now selects a single product page through its display index before querying lots through `lots_product`. Cost movement aggregation uses the existing `stock_lot` index. Ledger totals group movements by party before joining contacts.

## Regression coverage

Run `.venv\Scripts\python.exe -m pytest -q`. The added cases check the 15-piece and 12-piece FIFO example, acquisition/available/selling average distinctions, bill-book search and duplicate protection, form posting and current due, dated returns, unknown cost, and backup/restore from schema 5 with owner verification.

Baseline screenshots are in `build/v7/before`. Version 1.7 screenshots are in the matching source and packaged QA folders under `build/v7`. The smoke command opens an isolated practice workspace and writes a JSON diagnostic result and captures. Purchase/return, settlement, PDF and backup checks run through the Windows application and synthetic data.

## Release verification

| Check | Result |
|---|---|
| Automated regression suite | The first 1.7 run passed all 161 tests in 249.53 seconds. The later Sales layout check passed in 3.01 seconds when the headless test used a fixed 1366×749 viewport. The Windows capture independently confirmed Payment and Remaining are visible together. |
| Packaged Windows diagnostic | Passed. Captured 35 screens and exercised FIFO, invoice PDF, credit and collections, supplier bills, expenses and transfers, arrivals, partial cancellations, supplier refunds, stock returns, undo, reset, backup and restore. |
| 1366×768 at 125% Windows scaling | All seven pages and the Sale and Purchase dialogs fit inside the usable desktop. Save controls stayed visible and Settings scrolled. |
| Schema 5 upgrade on a populated copy | All original rows preserved across 12 tables. Schema 6 integrity check, foreign key check and pre-upgrade safety snapshot passed. |
| Practice guide | The isolated exercise checkpoints, illustrations of owner operations and verified financial figures passed the walkthrough script. |
| Schema 5 backup restore | Passed in an isolated shop. Original transaction reference and current owner credentials were retained. |
| Inno Setup dry run | Installed into an isolated Windows folder with a separate installer identity. All 553 files from the release staging folder matched by SHA-256. The test also verified that the old program source archive was removed in the isolated folder. The production installation was left on 1.6.0. |

The application deliberately keeps existing per-stack freight posting. A single freight charge spanning different models requires the client to choose an allocation and refund rule before it can be posted. The release was exercised on this Windows host. Upgrade and recovery tests used test copies of SQLite data.

## Changed files

| Area | Files |
|---|---|
| Database and values | `mobile_desk/database.py`, `mobile_desk/values.py` |
| Posting and reporting services | `mobile_desk/services/parties.py`, `products.py`, `purchases.py`, `reports.py`, `sales.py`, `stock.py` |
| Windows application and forms | `mobile_desk/app.py`, `mobile_desk/ui/common.py`, `main_window.py`, `products.py`, `report_page.py`, `settings.py`, `transactions.py` |
| Tests and benchmarks | `tests/test_simple_shop.py`, `test_import_purchasing.py`, `test_purchase_overview_ui.py`, `test_ui.py`, `tools/benchmark_business.py` |
| Version and packaging | `mobile_desk/__init__.py`, `pyproject.toml`, `installer/MobileDesk.iss`, `installer/version_info.txt`, `tools/release.py` |
| Documentation and practice | `README.md`, `USER_GUIDE.md`, `BUSINESS_RULES.md`, `DATABASE_SCHEMA.md`, the three release documents in `docs/`, `practice/Start-Practice.cmd`, `practice/Practice-Guide.md` and its generated HTML, `practice/China-Imports-And-Returns.md`, `tools/render_practice_guide.py` |
