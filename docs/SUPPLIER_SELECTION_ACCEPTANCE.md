# Supplier and customer selection — Mobile Desk 1.4.0

Repeated purchases must remain separate purchase records attached to one saved supplier account. Choosing a supplier or recording a later payment must not silently create another contact or invoice.

## Delivered behavior

- Purchase and sale contact fields select saved accounts. Choose / add opens Existing suppliers/customers first; New supplier/customer is an explicit second tab.
- The existing list searches name/phone, scrolls, pages at 100 accounts, and displays phone, address and current role-specific balance.
- Supplier payments and customer receipts use a non-editable dropdown and Choose from list. Their chooser cannot create contacts.
- Duplicate normalized names are blocked in the service transaction, including inactive or other-role contacts. Editing unchanged legacy duplicate contacts remains possible; renaming a contact into another account is blocked.
- Legacy duplicate labels identify the account and contact details. No account merge, deletion or ledger rewriting occurs.
- Suppliers and Customers explain combined account balances; Purchases explains one row per purchase.

## Verification

Automated checks cover selecting/creating/cancelling contacts, duplicate rejection, legacy duplicate identity, paging, payment without selection, no purchase/invoice created by a payment, and two purchases sharing one supplier account with an accurate combined balance. Native Windows smoke captures include both purchase chooser tabs and the payment list. Existing trading, cost, reports, backups, reset and undo checks remain required by the release build.
