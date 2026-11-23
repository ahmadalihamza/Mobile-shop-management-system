# Mobile Desk 1.7 client feedback matrix

Baseline `aeb8618` is Mobile Desk 1.6.0, schema 5. The feature branch is `mobile-desk-1.7-simple-shop`. Review covered the source, posting services, schema, backup flow, UI and existing tests. Baseline diagnostics use a separate synthetic shop.

| Client expectation | Assessment at baseline | 1.7 approach |
|---|---|---|
| Offline stock, sales, cash and statements | Already implemented | Reuse the SQLite services and group the three account destinations. |
| FIFO and original selling, cost and RMB snapshots | Already implemented | Keep posted allocations. Display reference averages and a read-only FIFO sale estimate. |
| Different cargo per stack, even for the same model | Already implemented | Show entered stacks, exact cargo in PKR and landed costs. Keep China per-stack and local per-piece entry. |
| Arrival, returns, credits and confirmed refunds | Already implemented | Put actions under the selected purchase and preserve owner checks. |
| Historical purchase average | Already implemented | Keep net acquisitions including incoming purchases. Show current available-stock average separately. |
| Weighted selling average and model reports | Improve UI and read calculations | Use net revenue divided by net pieces in the chosen dates. Returns are dated when posted. A nonpositive denominator or negative net revenue produces an unavailable average. Preserve period and gross-sale summaries. |
| Daily dashboard, outstanding balances and receipts | Improve UI | Show net sales, actual sale/return quantities, gross profit when known, positive dues and separate receipts. |
| Credit and later payments | Already implemented | Reuse the existing ledger and oldest-bill settlement for current dues. |
| Physical bill book number | Needs additive schema change | Store an optional separate reference, keep generated IDs, reject duplicate manual numbers, preserve historical references. |
| Responsive stock/search/report views | Improve UI | Measure baseline, page stock before lot aggregation, group ledgers before joining parties, debounce search and limit rendered rows. |
| Owner controls, backup, restore, reset, undo and audit | Already implemented in services | Retain protection and add audit access from Settings. |
| One freight charge across different models | Not confirmed | Existing charges belong to each entered stack. A future parcel charge would need an immutable freight header and explicit per-stack allocations reconciled to the converted total. Client must confirm manual allocation or an agreed quantity, value or weight rule and how partial refunds apply. |
| Replace FIFO or invent due dates | Not confirmed | Keep FIFO and label the overview Outstanding customers. |
