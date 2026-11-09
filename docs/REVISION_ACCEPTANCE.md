# Mobile Desk 1.2.0 revision acceptance

Revision date: 1 October 2026. The latest user instruction supersedes historical import and makes supplier payables mandatory. Scope: retain the offline native app and costing engine, simplify its daily forms, add a complete supplier ledger, and start production with no historical business entries.

## Decisions

Keep: offline native desktop, quantity stock, broad independent catalogue, manual products, FIFO, fixed purchase FX/costs, multi-item invoices, partial customer payments, linked returns, cash/bank, practical reports, printing/CSV/PDF, safe voids and backup/restore.

Improve: six useful dashboard figures; separate supplier/customer accounts; catalogue inside Stock; conditional RMB, variant, carry and split-payment fields; default full-payment sales; explicit supplier bill separate from landed stock cost; per-bill remaining balances; partial search inside reports; plain saved/payment/type labels.

Remove: automatic Excel seed, historical import tooling in production, historical-return/stock-verification menus, source model/legacy settlement reports, private client migration reports in release.

Add: supplier partial/later payment history, payable statements/outstanding, supplier opening/advances, separate transport payments without double profit deduction, archived clean-start operation, retired history rejection at restore/startup.

## Clean production evidence

The former database was backed up and archived under LocalAppData/MobileDesk/archives/BeforeCleanStart_20261001_132626_697563. All business entities now contain zero rows, including products/parties, sales, purchases, payments, stock, returns, adjustments, transfers and import evidence. Shop configuration and the default Cash account remain; monetary openings reset to zero. Five account references created only by the retired import were also removed, using the former database audit/evidence and the pre-import snapshot to distinguish them from legitimate configuration. The catalogue SHA-256 was unchanged: 07b76b6be8ed656b72e7b2306993930c2210d66fa0e9797d58fbb4889afc02be.

## Verification

The complete automated suite passed **73 tests** with no failures (docs/qa/tests.xml). It covers sales/purchases/stock/profit, exact rounding, historical FX snapshots, returns and correction dependencies, customer/supplier balances and later payments, role separation, oldest-bill settlement/advances, separate carry payments, atomic failure, catalogue updates/search, native form submissions, clean start, retired backup rejection, and backup/restore/restart.

The packaged executable and source application also passed a native Windows diagnostic capturing 17 screens and exercising manual products, local/China purchases, multi-lot FIFO, a partial sale, collections, supplier payment and per-bill dues, returns/refund, expenses/transfers, profit, invoice PDF and backup/restore. The final packaged and installed binary checks are recorded separately in docs/qa/revision-release-checks.json and its referenced native smoke result.

Retired migration-only tests/tooling are archived under reference/retired-excel-import and excluded from the release; ordinary trading, catalogue and recovery tests remain active.

The design is based on the earlier workbook requirements analysis and desk research. No observed client usability session or physical stock count has occurred; the owner must enter verified opening quantities and balances before actual trading. Catalogue coverage is broad reference data, not a claim of complete verified phone specifications.
