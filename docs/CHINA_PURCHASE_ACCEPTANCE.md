# China purchasing, average costs and secure returns — Mobile Desk 1.5.0

## Client-visible changes

Weighted Average Purchase Price is available in Stock & Products, product details and current-stock reports. Its numerator is original landed acquisition cost net of supplier returns/cancellations, and denominator is net purchased quantity. Existing FIFO sale allocations and saved costs remain unchanged. Opening and awaiting-arrival purchases count in the acquisition overview, while awaiting-arrival stock is unavailable for sale and excluded from available stock value.

Successfully saved purchases remember supplier and trading type for the next form, including across app restarts. Unsaved forms and opening-stock entries do not overwrite the remembered trading choice. An inactive supplier is not automatically selected.

China carry is entered once as the total for the whole stack. Each product row is one stack, including repeated rows for the same product when charges or prices differ. Every stack snapshots its entered charge, currency, quantity and converted total; its saved exchange rate converts the charge once. The converted carry is included in landed cost and average cost; supplier-billed carry is included in the supplier bill. Exact-paisa allocation may create two underlying FIFO cost portions differing by one paisa, but normal purchase reports and the return form keep the original stack together. Local carry retains its PKR-per-piece workflow, and existing pre-upgrade China carry remains PKR without reinterpretation. Cash / Bank payments remain actual PKR.

Awaiting-arrival purchases are entered without stock movements. Physical receipt adds only uncancelled pieces at original costs and cannot be repeated or predate a previous cancellation. Full and partial supplier returns remove only available original lots; pending cancellations reduce ordered quantities without creating negative stock.

All finalized purchase returns, cancellations and confirmed refunds require owner credentials and a review confirmation. A return creates supplier credit and preserves original purchases and payments. Refunds add money only when confirmed; supplier/carrier claims and actual refunds remain separate. Refunds cannot exceed unrefunded credit or refundable paid/available balances. Supplier credit reused against another purchase cannot also be refunded. Audits include owner identity, dates, purchase reference, reason, quantities, costs, credits and confirmed refunds.

Existing purchase Undo also requires owner credentials, and cannot reverse purchases with return history. Payment corrections cannot remove the financial basis of a recorded return/refund. Return and refund histories are immutable. External carry not credited on a return is a cost loss, with carrier recovery recognized on confirmed receipt.

## Upgrade and validation

Schema 4 → 5 migration adds stack records, fields, return/refund tables and ledger views, and preserves existing cost snapshots and transactions. A pre-upgrade SQLite safety copy is created automatically. Existing backups remain restorable with current owner authorization. Full reset creates a new empty schema and retains the configured owner credentials.

Automated tests cover weighted acquisition averages, exact RMB calculations, old PKR compatibility, pending availability, remembered selections, authenticated full/partial returns/cancellations/refunds, sold-stock and chronological guards, repeat-submit protection, no unconfirmed cash, statements/profit/carry recovery, immutable history, schema upgrade and real Qt forms. Native Windows source and packaged flows capture the new forms and reconcile their stock, balances, cost and refund results. No client data is seeded into release packages or altered by test runs.
