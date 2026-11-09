# Form simplification review — 22 October 2026

Reviewed the existing purchase, sales/returns, payment, balance-adjustment, contact, expense, transfer, product and settings forms. This review is based on the actual Mobile Desk screens, defaults and save requirements. The owner asked to remove reason entry now, and review other candidates before changing them.

## Changes implemented in 1.6.0

- Purchases now lists Products / phones using the original saved purchase descriptions. Multiple products appear together; repeated stacks or one-paisa cost allocations do not duplicate a phone name. Full names are available in the cell tooltip and batch details.
- Removed manual reason input from supplier returns/cancellations, customer returns, balance adjustments, Undo Last Entry, selected purchase undo, and sale/payment/expense/transfer/adjustment/customer-return corrections.
- Action descriptions are generated automatically. Existing history and any older written reasons stay intact. Owner credentials, refund confirmation, quantities, dates and dependency checks remain in force. This release does not alter the business schema.

## Candidates for the owner's next decision

These are proposals only; they are not changed in this release. Optional fields already accept a blank value, so hiding them would reduce clutter rather than remove an existing requirement.

| Screen | Current field | Suggested simplification | What should remain available |
|---|---|---|---|
| New Purchase | Batch reference | Keep the automatic number and hide the editable field under Add reference. | Optional supplier invoice/reference for matching paperwork. |
| Purchase refund | Refund reference and Notes | Put both under Add details, collapsed initially. | Reference/notes when needed to identify a bank or supplier refund. This would also give the owner-password field more visible room. |
| Transfer between accounts | Reference and Notes | Put both under Add details. | From, To, Date and Amount remain visible. |
| Expense | Category and Notes | Put both under Add details. | Description, Date, Amount and Paid from remain visible so the expense is identifiable. |
| Owner-authorized return, undo, reset and restore | Owner username, already prefilled from the configured owner | Display the configured owner as text and ask only for the password. | Owner setup/change-password must still identify the owner. Authentication stays in the service, not just the screen. |
| China purchase product table | Rate repeated on each product row, plus the batch default rate | Show one default rate, with an optional Different rates in this purchase control for row overrides. | Different saved stack rates and all historical snapshots must stay supported. |
| Add exchange rate | Notes | Hide under Add note. | Date and the actual PKR-for-1-RMB rate remain visible. |

## Fields to retain

Product, quantity, purchase/selling price, actual exchange rate, total stack carry and its currency determine stock cost and profit. Supplier/customer selection identifies the correct balance. Shipment arrival state prevents selling goods that have not arrived. Cash/bank account and actual payment/refund amount determine real money movement. Owner password and the return/refund confirmation prevent unauthorized or accidental financial reversals.

Product specifications, contact address/roles/availability and transaction notes already have optional collapsed controls in several forms. Removing those hidden options would give little improvement to normal daily entry. They can remain available for the occasions when the owner needs them.

Recommended order for a later change: collapse optional reference/notes fields first; then consider password-only owner authorization; then review whether hiding per-row exchange rates fits the client's actual purchasing routine.
