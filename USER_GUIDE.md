# Mobile Desk — shop guide

Mobile Desk works on this Windows computer without internet. Every amount is in PKR unless an RMB purchase price is explicitly shown. Stock is counted in pieces; no IMEI is needed.

## Begin using the clean shop

Enter your shop name on first launch. In Cash & Bank, add the bank accounts you use and set actual opening money balances before recording payments. Old spreadsheet entries have not been carried into this shop.

The owner should personally open Settings → Owner & Reset → Set owner password before staff use the software. Choose an owner username and a password of at least 8 characters, confirm it, and keep it safely. There is no default password. Reset and Restore Backup need these credentials. Change owner password requires the current password. Five wrong attempts block owner authorization for one minute, even after restarting the app. Keep the whole MobileDesk data folder safe; the owner-security.json file holds the password hash, never the plain password.

In Stock & Products, add the products you actually trade. Use Mobile Catalogue to search a worldwide reference, or Add Product Manually and enter a useful product name. Brand, model, RAM, storage, color and variant are optional details. Missing catalogue names never block trading. Search examples: `15 pro`, `a55`, `note 14`.

For stock physically present at the starting date, use New Purchase → Opening stock. Enter counted quantities and the actual unit cost. Opening stock does not create a supplier debt or a cash payment.

Add customers and suppliers only as needed. Open their accounts and use Opening / adjust balance to enter any agreed starting debt or advance. No reason entry is needed; the action is described automatically. These figures must be checked by the owner; the program cannot infer them from older purchases.

Sales and Purchases list individual transactions: each saved invoice/purchase has its own row, including repeat purchases from the same supplier. Customers are buyers and show what they owe the shop. Suppliers are businesses the shop buys from and show what the shop owes them. Reuse one saved account for each person/business so its balance combines all its bills and payments.

## Make a sale

Sales → New Sale. Add one or more products, quantity and selling price. Paid in full is selected by default, with Cash as the initial account. Select a bank if appropriate. A walk-in paid sale needs no customer.

For a partial receipt choose Part payment, choose the customer and enter what was received. Pay later / credit records no receipt and requires a customer. Split between two accounts appears only when needed. The fixed total and remaining balance are shown above Save.

Saving reduces stock, records the receipt and saves the original cost used for profit. Insufficient stock or invalid data prevents the entire sale from saving.

Open a sale to view/print its invoice or save a PDF. Paid at sale and Credit at sale describe the original invoice. The customer account shows later payments and current remaining bills.

## Receive money later

Customers → search the name/phone → Receive Payment. Choose the date, actual amount and Cash/Bank account. Each receipt stays in history. It reduces the existing balance; it does not create another sale.

Open account shows the statement, bills and remaining balances, payments and invoices. On-account payments and advances settle the oldest unpaid bills first. Negative customer balance means the shop holds customer credit.

## Buy phones locally

Purchases → New Purchase → Local purchase. Select a supplier, add the products, quantities and purchase prices. If paid now, select Record a payment from Cash / Bank now and enter the actual amount, or Pay full total. An unpaid purchase requires a supplier so the debt cannot be lost. A fully paid purchase can omit the supplier.

Use Choose / add supplier. The Existing suppliers tab opens first: search by name or phone, select the correct row and click Use Selected Supplier. To buy from a new business, switch to New supplier, enter its name and phone, then Save New Supplier. Choosing/creating the contact does not save a purchase; review products, prices and payments, then Save Purchase. Future purchases from this business should select its existing account.

The purchase list shows Products / phones using the names saved on that purchase. Multiple phone names appear together, and repeated stacks of the same phone are listed once. Hover over the cell to see its full contents or open the batch for quantities and prices. Editing a product name later does not rewrite its original purchase description.

Duplicate names (ignoring case, punctuation and spacing) cannot create another contact. An inactive contact or a contact needing a second customer/supplier role should be edited instead. For genuinely different businesses with similar names, include the location in the name. Older duplicate accounts are labelled with their account number and contact details so you can distinguish their separate histories; they are not automatically combined.

Supplier bill is what is owed to the supplier; Stock cost also includes any transport/carry entered. Stock increases automatically when the purchase saves.

## Buy in RMB / from China

Select China import (RMB). Enter RMB price and PKR for 1 RMB. The suggested rate is copied into the product line when it is added; each line can retain its own rate. Changing a default after adding a line does not silently change that line. Check the rate in the table before saving.

Select Add transport / carry costs when needed. Carry is PKR per piece. It increases the stock cost used for profit. Select Additional costs are included in the supplier bill only when the supplier actually charges them. Otherwise they are separate from the supplier debt; record actual transport money paid now, or open the purchase later and use Pay transport / carry. Do not enter the same carry again as an Expense.

Supplier payments are recorded in PKR at the amount actually paid. The original RMB price and purchase rate remain visible in the batch and China report. A new rate never recalculates old bills, stock costs or old profit.

From version 1.5, the next purchase remembers the type and supplier from the last successfully saved trading purchase. You can change either before adding product lines. Cancelled forms do not change the remembered choice, and entering Opening stock does not replace the regular purchase preference.

For China imports, enter carry as **one RMB total for the whole stack**, not per phone. Each product row is one stack: set its pieces, the phone price per piece, and that stack's total carry. Add the same product again for another stack with a different price or carry. You can set a default carry before adding a stack, or type the total in its row. The saved exchange rate converts both the phone price and the whole stack charge. Example: 6 phones at RMB 500 each plus RMB 150 carry for that whole stack, at PKR 40 per RMB, cost (6 × 500 + 150) × 40 = PKR 126,000 total, or PKR 21,000 per phone. The carry is charged once. A 30-piece stack can have a completely different total carry charge.

The app divides the converted stack carry across its pieces automatically. It preserves the exact charge even when division leaves a rounding remainder; FIFO cost portions may differ by one paisa, while the entered stack and its total stay together in the purchase history and return form. Choose PKR carry only when the China carrier actually charges PKR; it is still a whole-stack charge. Local purchases retain their existing PKR-per-piece carry workflow. Cash / Bank payments and confirmed refunds are always entered in actual PKR. Existing saved per-piece PKR carry is kept as recorded; upgrading never converts or multiplies old amounts again.

### Record stock that has not arrived

In New Purchase, set Shipment to Awaiting arrival before saving an order entered ahead of delivery. Its bill and actual payments are recorded, but those phones are unavailable for sale and excluded from physically available stock value. When it arrives, select the purchase and click Mark received, enter the real arrival date, confirm physical receipt and save. Only uncancelled pieces become available; arrival cannot be recorded twice.

### Cancel a shipment or return purchased stock

1. Select the original purchase in Purchases and click Return / Cancel. Awaiting-arrival shipments use Purchase Cancellation; received shipments use Stock Return to Supplier.
2. All eligible quantities are selected initially. Keep them for a full cancellation/return, or reduce Return now to the partial quantities being sent back. Sold pieces cannot be returned until their actual customer return is recorded.
3. Enter the return/cancellation date. Review the purchase, pieces, landed cost removed and supplier bill credit. There is no reason field to fill in.
4. If a refund has actually arrived, check Money has actually been received back, enter the actual PKR amount/account and select Supplier or Transport / carrier. Otherwise leave it unchecked; the supplier credit remains in the account and no cash is invented.
5. Enter the owner username/password, tick the review confirmation and click Authorize and Finalize. Incorrect credentials or invalid quantities/refunds save nothing. Original purchase lots and payments stay in history; dated return entries reverse eligible stock and supplier charges.
6. For a refund received later, select the purchase, open Returns / refunds, select the return/cancellation and click Confirm refund. Review the available credit, actual money received, account and date, then authenticate the owner and confirm. Partial refunds and separate carrier refunds can be recorded over time. Supplier credit already used against another purchase cannot also be refunded.

Supplier refunds settle supplier credit, not sales revenue or profit. Returned external carry that the supplier does not credit is shown as Purchase return cost loss in Period Profit; any actual carrier refund is recovered in the period received. Original RMB prices, saved rates and landed costs remain unchanged. The history shows the authenticated owner, automatic action description, date, quantities, credits and refunds. Older written descriptions remain in history. Returns and refunds are permanent history rather than deletable entries. If a finalized return itself was entered incorrectly, keep its evidence and have the owner record the real corrective purchase/payment; do not silently delete a refund that represents money received.

Purchase Undo is for a genuine entry mistake and now also requires owner credentials. It cannot undo original records once a purchase return exists. Use the return/cancellation workflow for a real shipment claim so cash is only restored when the refund is confirmed.

## Pay a supplier later

Suppliers → search supplier → Pay Supplier. Enter the actual date, PKR amount and payment account. Every payment is retained. Open account shows purchases, payments, statement and which bills remain unpaid. Negative supplier balance is an advance held by the supplier. Customer and supplier balances remain separate even when one contact has both roles.

From Cash & Bank → Payments → Pay Supplier, select the supplier from the dropdown or click Choose from list for a searchable, scrollable saved-supplier list. Names cannot be typed into the payment selection. Check the selected account and current balance, then save the actual payment. This records a payment against that account; it does not create a supplier, purchase or invoice. Receive Customer Payment uses the same saved-customer selection.

## Stock and profit

Stock & Products shows available pieces and remaining stock value. Open Product details for purchase lots, saved rates and sales history. Purchases add stock; sales remove stock; invoice returns restore the original purchase costs.

The program uses FIFO: oldest available purchase stock is costed first. It never replaces older costs with a latest price. Reports → Product Sales / Profit or Period Profit shows selling value less the allocated purchase cost, with recorded shop expenses and customer discounts shown separately. Supplier payments and account transfers do not change profit.

Average Purchase Price (PKR) is a separate overview: total original landed acquisition cost divided by total acquired pieces across all posted batches, less supplier-returned or cancelled quantities at their original costs. It includes opening stock and awaiting-arrival purchases. Sales do not change this historical acquisition average, so a sold-out product may still show an average; a product with no remaining acquisition history shows no average. Available Stock cost continues to use actual remaining FIFO lots. Example: sixteen unsold phones with total landed cost PKR 387,000 have an average of PKR 24,187.50 per phone.

## Returns and mistakes

Select the original invoice in Sales → Return. Enter the returned quantities and any actual refund account/amount. The returned value reduces the customer balance and the original stock cost is restored. A walk-in return requires a full refund.

Only return saleable goods to available stock. Damaged/unsaleable goods must not be recorded as normal returns in this quantity-trading workflow.

For the most recently saved business transaction, click Undo Last Entry at the bottom of the sidebar. Review its type, reference, date and amount and click Undo This Entry. No reason entry is needed. Purchase undo still requires the owner credentials. It supports sales, purchases/opening stock, returns, later customer/supplier payments, transport payments, expenses, transfers and new balance adjustments. Unsaved forms can be cancelled; product/settings edits are outside transaction undo.

For a specific wrong sale or purchase, select it in the relevant list and use Undo selected entry, confirm the action, then post the corrected entry. The original remains visibly Voided for a reliable history, with an automatic correction description. Undo reverses its stock and attached payments. Correct dependent sales/returns first if stock from an earlier purchase has already been used. Later on-account collections/payments remain in history and may become advances until the replacement bill is entered. Undo does not silently delete history or automatically post a replacement.

Wrong later payments and balance adjustments can be corrected from the account's Payments or Balance adjustments tab. Cash & Bank also provides payment/expense/transfer correction. Original invoice receipts are corrected with their invoice.

## Reports

Choose a report and simple From / To dates. Reports include daily/monthly sales, product sales/profit, customer/supplier statements and outstanding balances, current stock, local/China purchases, period profit, returns and cash/bank summary. Outstanding is as of To; current stock is the quantity available now. Statement selection searches the appropriate customer or supplier.

Use the report search box to find products, customers, suppliers or batches by partial text. Export CSV or Print / PDF when useful. Excel can open the exported report; it is not an import into the shop database.

## Backup and recovery

At the end of each trading day use Settings → Backup & Restore → Backup Database. Save to a USB drive or another disk, and keep more than one dated backup. A backup includes the business database and separate catalogue.

Restore Backup shows the backup date, checks the files and asks for the owner username/password before replacing the shop. It saves the current data in a safety backup. Your current owner credentials remain in place even when restoring an older backup; they are not replaced by business backups. Old archives containing retired Excel-imported history cannot be restored into this clean shop.

Settings → Mobile Catalogue → Import Catalogue Update accepts a Mobile Desk JSON package. Catalogue updates add/reference phones without changing shop products, historical descriptions, sales or purchase costs. Manual products remain available.

## Clear practice entries and start fresh

1. Open Settings → Owner & Reset. Set the owner password first if it has not been configured.
2. Click Reset All Business Data. Review the records being cleared.
3. Enter the owner username/password and type `RESET` exactly.
4. Click Back Up and Reset All Data. Cancellation or an incorrect password clears nothing. If the automatic backup fails, reset stops without replacing the records.
5. The app returns to an empty dashboard and shows the safety backup path. Before trading, enter the actual counted opening stock and agreed customer/supplier and cash/bank opening balances.

This clears all shop products and aliases, customer/supplier contacts, purchases, sales, stock, payments, returns, expenses, transfers, opening/adjustment entries, saved exchange rates and transaction history. Money balances become zero and invoice numbering starts again at 1. Shop details, invoice prefix, backup preference, cash/bank account names, reference catalogue and owner credentials remain. Older backups are retained. Reset is a fresh business start; it is not permanent erasure of saved backups.

To undo a full reset, use Settings → Backup & Restore → Restore Backup, choose the safety backup shown after the reset, and enter the owner credentials. This replaces everything entered after the reset with the earlier saved state, so first save/export any later work you need. The app also saves a safety backup of that current state.

Do not reset simply because a new month begins. Stock, bank balances and unpaid customer/supplier balances normally continue across months. Use Reports → From / To to see only the new month's activity. For one entry mistake use Undo; for a completely fresh learning session use Reset.
