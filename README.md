# Mobile Desk 1.6.0

An offline Windows desktop application for a mobile-phone trader. Native PySide6, SQLite and quantity stock; no browser or network is needed for trading. Local owner credentials protect reset and backup restore.

Daily work: sales, local/RMB purchases, customer collections, supplier payments, stock, cash/bank and reports. China imports support whole-stack carry, shipment arrival tracking, weighted purchase prices, and owner-authorized returns and confirmed refunds. Purchases list the saved phone names. The reference catalogue contains 19,667 names across 122 brands and remains separate from shop products. Manual products are always supported. IMEI is never required.

## Start

Download the [Windows installer](https://github.com/ahmadalihamza/Mobile-shop-management-system/releases/download/v1.6.0/MobileDesk-1.6.0-Setup.exe) or the [portable Windows build](https://github.com/ahmadalihamza/Mobile-shop-management-system/releases/tag/v1.6.0). Extract the portable ZIP before running `MobileDesk.exe`. Records live in `%LOCALAPPDATA%/MobileDesk`, independently of the executable. Enter your shop identity, set the owner's credentials in Settings → Owner & Reset, then enter actual opening stock/balances and new business activity. See the [user guide](USER_GUIDE.md). Upgrading does not reset existing records.

New installations start with an empty business database. The downloads contain no shop data, spreadsheets, backups, or owner credentials.

## Run from source

Use 64-bit Python 3.12. From PowerShell in the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run_mobile_desk.py
```

For a separate practice workspace, run with `--demo` or use [Start-Practice.cmd](practice/Start-Practice.cmd). See the [practice guide](practice/Practice-Guide.md) and [China imports and returns exercises](practice/China-Imports-And-Returns.md).

Run `.venv/Scripts/python.exe -m pytest -q`. Build with `powershell -NoProfile -ExecutionPolicy Bypass -File build_windows.ps1 -SkipInstall` after dependencies are installed. Native packaging uses PyInstaller and optional Inno Setup. SHA256SUMS.txt identifies delivery files.

## Reliability

One transaction saves each sale/purchase, stock movement, receipt and ledger impact. Failed saves roll back. Money uses integer paisa and exact decimal conversions; FIFO allocations preserve original lot costs. Exchange-rate changes affect new purchases only. Controlled voids keep the original record and log the action automatically. Backup/restore validates checksums, database integrity and foreign keys, then protects the current files with a safety backup.

Undo Last Entry shows the most recently saved supported transaction for review before reversing it. No reason entry is required. Reset All Business Data requires owner credentials, explicit RESET confirmation, and a verified safety backup. It clears business records and money openings, preserving shop identity, account names, catalogue and owner protection. Use report dates at month end; resetting would also clear unpaid balances and stock. Password protection is local application authorization, not database encryption or protection from a Windows administrator manipulating files.

Catalogue provenance and limitations are documented in [CATALOGUE.md](CATALOGUE.md). The project is licensed under [GPL-3.0-or-later](LICENSE); see [third-party notices](THIRD_PARTY_NOTICES.md).
