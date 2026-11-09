# Database schema — version 5

Business database: `%LOCALAPPDATA%/MobileDesk/data/mobile_desk.db`. Catalogue: separate `mobile_catalogue.db`. Foreign keys, WAL, full synchronization and bounded locking are enabled. Writes are atomic; connections are short-lived. Existing schema upgrades save a pre-upgrade database snapshot and check foreign keys before commit.

| Entity | Purpose |
|---|---|
| products, product_aliases | Actual shop products with optional catalogue reference and partial search aliases |
| parties | Customer/supplier roles, optional contact details |
| accounts | Cash/bank configuration and explicit opening balances |
| purchase_batches | Purchase date/type/supplier, total landed cost, supplier bill, carry billing decision |
| purchase_items | Quantity and fixed currency/RMB/rate/converted/carry/landed cost snapshots |
| purchase_stacks | Original entered stack quantity, charge basis/currency/input and exact converted carry/landed totals |
| purchase_returns, purchase_return_items | Owner-authorized dated return/cancellation and original-lot quantities/credits |
| purchase_refunds | Immutable, owner-confirmed supplier/carrier cash receipts linked to a purchase return |
| stock_movements | Append-only changes per purchase lot |
| sales, sale_items | Invoice header, quantity/rate/value, original allocated cost and descriptions |
| stock_allocations | FIFO units and original costs attributed to sale items |
| returns, return_items, return_allocations | Invoice returns and original-cost restoration |
| payments | Separate receipts, collections, supplier/transport payments and refunds, with void history |
| party_adjustments | Dated opening/adjustment entries, explicitly CUSTOMER or SUPPLIER |
| expenses, account_transfers | Actual money movement for shop expenses and internal transfers |
| exchange_rate_history | Suggested rates for future purchases; never rewrites purchase items |
| settings, audit_log, operation_keys, schema_history | Configuration, correction trail, idempotency and schema versions |

Views: `lot_stock` derives remaining lot quantities, `money_ledger` derives cash/bank movements, `party_ledger` derives customer balances and `supplier_ledger` derives supplier balances. `payments.ledger_role` keeps supplier, customer and separate transport effects independent; `NONE` affects money only.

Purchase snapshot and stock-history triggers prohibit destructive rewrites. Void status removes ledger effects while explicit reversal stock movements retain history. Compatibility fields/tables introduced by the retired version-3 import remain for upgrade/backup compatibility, but no import routine is shipped and these tables contain no client history in the clean production database.

Catalogue updates operate on their independent database and preserve business records. Read CATALOGUE.md for the versioned update contract.

Owner authorization lives in `%LOCALAPPDATA%/MobileDesk/owner-security.json`, outside the `data` directory and business backup payload. It stores username, a random 16-byte salt, scrypt-32768-8-1 password hash, and durable failed-attempt/temporary-lock state. Password changes are atomically written. Reset/restore preserve this current identity; there is no plain password or default credential. The file is not a business record and is not encrypted. Protect the Windows account and data folder accordingly.

Reset stages a new schema-5 business database with selected shop/account configuration and zero openings. The current catalogue is copied from the verified safety snapshot. The `.restore-pending`, `.restore-new` and `.restore-old` directory protocol is shared by reset and restore; startup recovers an interrupted replacement before opening business services. The fresh database records a RESET audit entry naming the authorizing owner and safety backup, while the original transaction history remains in the backup/archive. New balance adjustments also emit a POST/adjustment audit record so Undo Last Entry can locate their actual record ID.

Version 5 adds shipment state/arrival dates, carry currency and original foreign carry snapshots. A whole-stack charge is converted once, then allocated exactly in paisa across immutable cost lots; a rounding remainder creates at most two cost portions for that stack. The purchase_stacks row preserves the original input. Existing costs remain PKR and existing purchases are treated as received. Arrival creates stock movements only for uncancelled pieces. Purchase returns reverse physical stock where applicable and issue supplier credit without changing original purchases/payments. Supplier/carrier refunds add money only through purchase_refunds and corresponding ledger views. Return/refund tables and original stack records reject update/delete. Audits retain authenticated owner identity and operation details; passwords never enter the business audit.
