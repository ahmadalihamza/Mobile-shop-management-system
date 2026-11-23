# Mobile Desk 1.7.0 — Simple Shop Edition

- Six daily destinations and a Settings utility. The sidebar offers New Sale, New Purchase and Receive Payment. Accounts has Customers, Suppliers and Cash & Bank tabs. Settings has activity history and Undo Last Entry.
- Dashboard shows net sales, pieces sold, monthly gross profit when verified, physical stock and positive dues. Separate receipt and incoming-stock totals sit above recent sales, recent purchases, best sellers and outstanding customers.
- Sales show phone names, invoice and bill-book references, paid at sale, current amount due and payment status. Open the invoice for PDF, returns and undo. Sale entry adds stock and price references, a read-only FIFO estimate, keyboard save and unsaved-entry confirmation.
- New Purchase shows cargo, pieces, landed value, supplier bill and amounts paid or due. Open a saved purchase for original cargo totals, stack snapshots, shipment status, payment history, receipt, cancellation and refund actions. Optional parcel references and per-stack rate overrides are revealed when needed.
- Stock adds available unit cost and date-filtered selling average beside acquisition average. Product details show incoming pieces, last prices, net sales and FIFO gross profit with parcel and sale history.
- Reports give direct access to Daily Sales, Monthly Sales, Available Stock and Product Profit. Detailed reconciliation is available in More Reports. Stock is paged in SQLite, and only one page of rows is rendered on screen.
- Database schema 6 adds the optional, unique bill-book number and a product display index. The upgrade path keeps original posted costs, legacy references, inventory movements, receipts and owner protection.
- Shared multi-model freight remains a client decision. Each existing cargo charge still belongs to its entered stack.
