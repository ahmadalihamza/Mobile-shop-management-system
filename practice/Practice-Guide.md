# Mobile Desk — complete practice workbook

For Mobile Desk 1.6.0. Follow the main trading day in order, then try the extra exercises. The figures below were checked against the actual application's calculation engine. These are fictional training prices, exchange rates and contacts, not market quotations. The additional China-Imports-And-Returns.md guide covers stack charges, arrival, supplier returns and confirmed refunds. Reason fields have been removed; the software records action descriptions automatically.

## 1. Open the separate blank practice shop

Double-click **Start-Practice.cmd** in this folder. It opens the installed Mobile Desk using a separate business folder:

`shop-data` inside the folder containing this guide.

Your normal shop is a different folder. In the practice window, check **Settings → Shop → Data folder** before entering anything. It must show the practice folder above. Use **Start-Practice.cmd** every time you return to these exercises. The regular Mobile Desk shortcut opens the normal shop.

The practice shop starts blank, except for the built-in reference catalogue. I have not loaded the example transactions: you will enter them yourself. If you have already used this practice folder, make a backup and reset it before repeating the main lesson, or restore your CleanSetup backup. Leave the normal shop alone.

Use **1 October 2026** for all new purchases, sales, returns, expenses and payments in this lesson. Use **30 September 2026** only for money/contact opening balances. Enter those dates explicitly; today's date may be different when you practice later. Set list/report filters to include these dates so your entries remain visible.

## 2. Understand how the software works

| Action | What it creates or changes | What it does not do |
|---|---|---|
| Catalogue search | Finds a reference phone name | Does not add actual stock |
| Add Shop Product | Creates a product you trade | Does not buy a phone or spend money |
| Opening stock | Adds counted stock at its starting cost | Does not create a new supplier bill or payment |
| Purchase | Adds a cost lot and stock; creates a supplier bill when appropriate | Does not mean the supplier has been paid |
| Sale | Reduces stock, saves the invoice and original allocated cost, calculates profit | Does not mean a credit customer has paid |
| Receive Payment | Reduces customer debt and increases Cash/Bank | Does not create a second sale |
| Pay Supplier | Reduces supplier debt and Cash/Bank | Does not change the original stock cost or deduct profit again |
| Return | Restores saleable stock at the original cost; credits the customer and records any refund | Is not a new purchase |
| Expense | Reduces Cash/Bank and reported profit | Is not an internal money transfer |
| Transfer | Moves money between your own accounts | Does not change total money, sales or profit |
| Undo | Reverses a saved transaction with an automatic action description; retains the original as Voided | Is not permanent deletion or automatic replacement |
| Full reset | Starts the business records and balances at zero after an owner-approved backup | Is not a routine month-end action or deletion of old backups |

The application works offline. It keeps a business database and a separate reference catalogue. A purchase's currency/rate/carry cost is saved with that lot. FIFO means the oldest available lot is used first when you sell. A later exchange rate or product-name edit does not rewrite the original invoice or purchase snapshot.

## 3. Configure the shop and owner

On the welcome screen, enter:

| Field | Practice entry |
|---|---|
| Shop name | Mobile Desk PRACTICE |
| Phone | Leave blank, or use your own practice contact |
| Address | Training only — no real shop records |

Open **Settings → Shop**. Set **Invoice prefix** to `PR-` and **Next invoice sequence** to `1`, then **Save shop settings**. Do this before recording any sales. The four lesson invoices will be PR-000001 through PR-000004.

Open **Settings → Owner & Reset → Set owner password**. Username: `practiceowner`. Choose your own password of at least 8 characters and confirm it. Keep it safely; there is no default password. This practice owner is separate from the normal shop's owner. Do not copy a published example password into a real shop.

Open **Cash & Bank → Accounts → Add account**. Create `Practice Bank`, type Bank, opening amount `0`, opening date 30 September 2026, Active checked. Keep the existing Cash account.

Under **Settings → Backup & Restore**, choose this preferred backup folder:

`Backups` inside the folder containing this guide.

Click **Backup Database** and choose `Backups\01-CleanSetup` (create it if needed). The app automatically generates a dated `.mdbackup` filename. This backup has your shop/account configuration but zero business records and openings. Keep it if you want to restart from an empty shop later.

## 4. Enter starting Cash and Bank balances

Open **Cash & Bank → Accounts**. Select each account → **Edit account**:

| Account | Opening amount PKR | Opening date | Negative opening? |
|---|---:|---|---|
| Cash | 500,000 | 30 September 2026 | No |
| Practice Bank | 300,000 | 30 September 2026 | No |

Save each. Expected total money: **800,000**. Set these before recording payments; an account with active transactions cannot have its opening amount/date changed through ordinary account editing.

An opening balance is money already present at the starting point. Do not also record it as a new customer payment.

## 5. Create three shop products

For the Samsung product, open **Stock & Products → Mobile Catalogue**, search `a55`, select Galaxy A55 and click **Create Shop Product**. Fill the product name and optional details below. If your selected reference has a slightly different display name, use the exact custom product name in this table for the lesson.

Repeat with a catalogue search for `note 14` for Xiaomi. For the used phone choose **Add Product → + Add Product Manually**; catalogue coverage is not required.

| Product name | Optional details | Other search names |
|---|---|---|
| Samsung Galaxy A55 8/256 Navy | Brand Samsung; model Galaxy A55; RAM 8; storage 256; color Navy | a55navy |
| Xiaomi Redmi Note 14 8/256 Black | Brand Xiaomi; model Redmi Note 14; RAM 8; storage 256; color Black | note14black |
| Practice Used Phone 6/128 | Variant Used; other details optional | used128 |

Enable **Brand, model and optional variant details** to see aliases. Multiple aliases are separated by semicolons. Keep **Active product** checked. IMEI is not needed.

Expected: three shop products, each with **zero** stock. Search `a55navy`, `note14black` and `used128` to check aliases. Creating a product alone must not increase stock.

## 6. Create customers and suppliers

Sales and Purchases show separate transaction rows. Customers and Suppliers show saved accounts with combined balances. Reuse a supplier's account for repeat purchases. In New Purchase, click **Choose / add supplier → Existing suppliers**, search its name/phone and **Use Selected Supplier**. Only use **New supplier** for a different business. Payments offer **Choose from list** and do not accept manually typed supplier names. Existing duplicate accounts show an account number; their histories remain separate.

| Screen | Action | Name | Role |
|---|---|---|---|
| Customers | Add Customer | Ali Dealer | Customer |
| Suppliers | Add Supplier | Karachi Supply | Supplier |
| Suppliers | Add Supplier | China Supply | Supplier |

Phone/address/notes are optional. For this main lesson keep contacts Active and do not give them both roles yet.

Open **Ali Dealer → Open account → Opening / adjust balance**. Date 30 September 2026, Adjustment **Opening balance**, amount `20000`. Leave **Shop owes customer (customer has credit)** unchecked. Expected Ali receivable: **20,000**.

Open **Karachi Supply → Open account → Opening / adjust balance**. Same date, Opening balance, amount `10000`. Leave the supplier-advance direction unchecked. Expected Karachi payable: **10,000**.

China Supply starts at zero. These opening debts do not move Cash/Bank or create current-day sales/profit.

## 7. Save a practice exchange rate

Open **Settings → Exchange Rates → Add exchange rate**. Date 1 October 2026; PKR for 1 RMB `40`; notes `Practice rate, not a live market quote`. Save. Rate history is a suggestion for new China batches; check the actual line rate before saving a purchase.

## 8. Enter opening stock

Open **Purchases → New Purchase**. Date 1 October 2026; Type **Opening stock (PKR cost)**; Batch reference `OPEN-TRAIN-1`. Leave the supplier unselected. Add:

| Product | Qty | Unit cost PKR | Total PKR |
|---|---:|---:|---:|
| Samsung Galaxy A55 8/256 Navy | 2 | 40,000 | 80,000 |
| Practice Used Phone 6/128 | 1 | 15,000 | 15,000 |

No payment and no carry cost. Click **Save Purchase**.

Expected: **3 pieces**, stock value **95,000**; Cash **500,000**, Bank **300,000**, Ali owes **20,000**, Karachi owed **10,000**, China owed **0**. Opening stock does not increase supplier debt or reduce money.

Save a backup in `Backups\02-Openings`. Restore this later to repeat the trading day without recreating products/contacts/openings.

## 9. Local purchase with supplier-billed carry and partial payment

Open **Purchases → New Purchase**:

| Field | Entry |
|---|---|
| Date / Type | 1 October 2026 / Local purchase |
| Supplier / Batch reference | Karachi Supply / LOCAL-TRAIN-1 |
| Product / Quantity | Samsung Galaxy A55 8/256 Navy / 3 |
| Price per unit PKR | 42,000 |
| Add transport / carry costs | Checked |
| Carry per unit PKR | 1,000 in the product line |
| Additional costs are included in the supplier bill | Checked |
| Record a payment from Cash / Bank now | Checked |
| Payment amount / Account | 79,000 / Practice Bank |

Save. The supplier is charging the carry, so supplier bill and stock cost are both **129,000**: 3 × (42,000 + 1,000). The new bill has **50,000** unpaid. With the earlier opening debt, Karachi's total payable is **60,000**.

Expected: **6 pieces**, stock value **224,000**, Cash **500,000**, Bank **221,000**. The older two Samsung units retain their original 40,000 cost; these three new units cost 43,000 each.

## 10. China purchase with external carry and partial payments

Choose **China import (RMB)** before adding products; the purchase type becomes fixed once a line is added. Set the default rate/carry before adding the line, then verify the actual line values.

| Field | Entry |
|---|---|
| Date / Supplier / Reference | 1 October 2026 / China Supply / CHINA-TRAIN-1 |
| Default RMB → PKR | 40 |
| Default carry / stack total RMB | 200 for the whole 4-piece stack |
| Product / Quantity / RMB price per unit | Xiaomi Redmi Note 14 8/256 Black / 4 / 1,000 |
| Actual line rate / Whole-stack carry RMB | 40 / 200 |
| Add transport / carry costs | Checked |
| Additional costs are included in the supplier bill | Unchecked |
| Record a payment now | Checked: 100,000 from Practice Bank |
| Transport / carry paid now | 3,000 from Cash |

Save. The whole-stack RMB 200 charge converts once to **8,000 PKR**, allocated over four phones as 2,000 each. Each phone costs 1,000 × 40 = **40,000 PKR**, plus allocated carry 2,000 = **42,000 landed cost**. Supplier bill **160,000**; stock cost **168,000**. Supplier debt **60,000**. Total external carry is **8,000**; **5,000** remains unpaid after the 3,000 payment.

Expected: **10 pieces**, stock value **392,000**, Cash **497,000**, Bank **121,000**, Karachi payable **60,000**, China payable **60,000**.

Open the batch to inspect saved RMB price, rate, converted cost, carry and remaining pieces. Never record this same capitalized carry again as an Expense.

## 11. Sale 1 — paid cash walk-in

Open **Sales → New Sale**. Date 1 October 2026; customer **Walk-in / select customer for credit**; add Samsung, Qty **1**, selling price **50,000**. Choose **Paid in full**, payment account **Cash**, paid amount **50,000**. Save.

Expected invoice `PR-000001`: total **50,000**, no debt, profit **10,000** because FIFO takes an opening unit costing 40,000. Stock **9 pieces / 352,000**; Cash **547,000**.

## 12. Sale 2 — multiple products, part payment and split accounts

Date 1 October 2026; customer **Ali Dealer**. Add:

| Product | Qty | Selling price PKR | Line total PKR |
|---|---:|---:|---:|
| Samsung Galaxy A55 8/256 Navy | 2 | 52,000 | 104,000 |
| Xiaomi Redmi Note 14 8/256 Black | 1 | 50,000 | 50,000 |

Total **154,000**. Select **Part payment**, then **Split between two accounts**. First amount **40,000** into Cash; second amount **60,000** into Practice Bank. Check the remaining balance is **54,000**, then Save Sale.

Expected `PR-000002`: paid at sale **100,000**, credit at sale **54,000**. Ali's total owed becomes **74,000**, including his earlier 20,000 debt. Cash **587,000**; Bank **181,000**; stock **6 pieces / 227,000**.

FIFO cost: Samsung units 40,000 + 43,000, Xiaomi 42,000; total cost **125,000**, gross profit **29,000**. The software does not simply multiply the latest Samsung cost by both units.

## 13. Sale 3 — fully credit

Date 1 October 2026; customer Ali Dealer; product Practice Used Phone 6/128; Qty **1**; selling price **20,000**. Select **Pay later / credit**; no receipt. Save.

Expected `PR-000003`: total/credit **20,000**, paid at sale **0**. Ali now owes **94,000**. Money accounts do not change. Gross profit **5,000**; stock becomes **5 pieces / 212,000**.

## 14. Sale 4 — paid bank walk-in

Date 1 October 2026; walk-in; Xiaomi Qty **1**, selling price **51,000**; **Paid in full**, account Practice Bank, amount **51,000**. Save.

Expected `PR-000004`: profit **9,000**, no customer debt. Bank **232,000**; Cash **587,000**; stock **4 pieces / 170,000**. The four invoices total **275,000**, with gross profit **53,000** before the later return, expenses and discount.

## 15. Receive a later customer payment

**Customers → Ali Dealer → Receive Payment**. Date 1 October 2026; amount **60,000**; receive into Practice Bank; reference `ALI-COLLECT-1`. Save.

Expected: Ali owes **34,000**, Bank **292,000**. No new sale or profit is created.

Open account → **Bills / balances**. The payment settles oldest balances first: the 20,000 opening debt is cleared; PR-000002 has **14,000** remaining; PR-000003 has **20,000** remaining. The invoice's printed **Paid at sale** stays the original amount; use the customer account for later settlements.

## 16. Pay suppliers later

| Supplier | Date | Amount PKR | Pay from | Reference | Payable afterward |
|---|---|---:|---|---|---:|
| Karachi Supply | 1 October 2026 | 60,000 | Cash | KARACHI-PAY-1 | 0 |
| China Supply | 1 October 2026 | 30,000 | Practice Bank | CHINA-PAY-1 | 30,000 |

Use **Suppliers → select supplier → Pay Supplier** for each. Expected money: Cash **527,000**, Bank **262,000**. These payments settle debts; they do not deduct purchase costs from profit again.

## 17. Return from Ali's invoice, with a partial cash refund

Find `PR-000002` in Sales, select it → **Return**. Date 1 October 2026. Set **Return now** to **1** on the Xiaomi row; leave the Samsung row at **0**. Returned value **50,000**. Refund now **20,000**, refund from Cash; notes `Practice customer return — saleable phone`. Save Return.

The return reduces the customer balance by 50,000, and the actual refund adds 20,000 back to what is owed: 34,000 − 50,000 + 20,000 = **4,000 owed by Ali**.

Expected stock **5 pieces / 212,000**; Cash **507,000**; Bank **262,000**. The phone returns at its original **42,000** cost. Gross profit reduces by **8,000**. Only record saleable goods as normal stock returns.

## 18. Pay the remaining external carry

**Purchases → CHINA-TRAIN-1 → Open batch → Pay transport / carry**. Date 1 October 2026; amount **5,000**; Pay from Cash; save.

Expected Cash **502,000**, remaining external carry **0**, China supplier debt still **30,000**, stock value still **212,000**. This is payment of a cost already included in stock, not another profit deduction.

## 19. Record shop expenses

Open **Cash & Bank → Expenses → Record Expense** twice:

| Date | Description | Amount PKR | Paid from | Category |
|---|---|---:|---|---|
| 1 October 2026 | Practice shop rent | 10,000 | Cash | Rent |
| 1 October 2026 | Practice delivery expense | 2,000 | Cash | Delivery |

Expected Cash **490,000**, total recorded expenses **12,000**. These are separate operating expenses; the delivery exercise is not the carry already entered on the China batch.

## 20. Transfer Cash to Bank

**Cash & Bank → Transfers → New Transfer**. Date 1 October 2026; From Cash; To Practice Bank; amount **50,000**; reference `CASH-TO-BANK-1`; Save.

Expected Cash **440,000**, Bank **312,000**, total money **752,000**. The transfer changes neither total money nor profit.

## 21. Agree a final customer discount

**Customers → Ali Dealer → Open account → Opening / adjust balance**. Date 1 October 2026; Adjustment **Agreed discount**; amount **4,000**. Save.

Expected Ali balance **0**. Money accounts do not change because no money was received. Period Profit separately deducts this customer discount, leaving **29,000 profit after expenses and discounts**.

## 22. Check the completed-day figures

| Measure | Expected result |
|---|---:|
| Active sale invoices | 4 |
| Gross pieces sold before the return | 6 |
| Returned pieces | 1 |
| Net pieces sold | 5 |
| Samsung pieces remaining / value | 2 / 86,000 |
| Xiaomi pieces remaining / value | 3 / 126,000 |
| Used phone pieces remaining / value | 0 / 0 |
| Total remaining stock | 5 pieces / 212,000 |
| Cash / Practice Bank | 440,000 / 312,000 |
| Ali customer balance | 0 |
| Karachi supplier balance | 0 |
| China supplier balance | 30,000 |
| Gross sales / returned value / net sales | 275,000 / 50,000 / 225,000 |
| Net cost of sold goods | 180,000 |
| Gross profit | 45,000 |
| Recorded expenses / customer discounts | 12,000 / 4,000 |
| Profit after expenses and discounts | 29,000 |

Dashboard: Today's sales **275,000** shows gross posted sales; Sales this month **225,000** is after returns. Purchases this month **297,000** excludes the 95,000 opening stock. Customers owe **0**; Suppliers owed **30,000**; Stock pieces **5**.

The dashboard's day/month sales figures above assume the computer is on 1 October / within October 2026. If you practice on another date, use the lesson's explicit report date range to check the totals; the dashboard's Today view follows the computer date. Current stock and overall account balances still show the existing practice position.

Save a backup in `Backups\03-CompletedDay`. This is the baseline for every extra exercise below. To reset an extra exercise, restore that completed-day `.mdbackup` using the practice owner's credentials. Restore replaces the later exercise entries too; it is a whole-shop snapshot.

## 23. Run every report

Open Reports. Set From **1 October 2026** and To **1 October 2026** unless stated otherwise. Click **Run report** after choosing the report. Clear any search filter before checking totals.

| Report | What to look for |
|---|---|
| Daily Sales | 6 pieces, Sales 275,000, Paid at sale 201,000, Credit at sale 74,000, Later collections 60,000, Returns 50,000, Net sales 225,000 |
| Monthly Sales | With From 1 October and To 31 October, October totals match the day above if you made no extra entries |
| Product Sales / Profit | Samsung sold 3, gross profit 31,000; Xiaomi sold 2, returned 1, gross profit 9,000; Used sold 1, gross profit 5,000. Customer discount is in Period Profit, not deducted from these product gross-profit rows |
| Customer Outstanding | No row for Ali because his balance is zero; negative advance balances appear in later exercises |
| Customer Statement | Select Ali from the actual dropdown list: opening brought forward 20,000, sale/payment/return/discount entries, final balance zero |
| Supplier Outstanding | China Supply 30,000; Karachi is absent because its balance is zero |
| Supplier Statement | Select Karachi or China; follow opening bill, current purchases and actual payments |
| Current Stock / Stock Value | Samsung 2 / 86,000; Xiaomi 3 / 126,000; Used 0 / 0; this report is current stock, not an old historical stock position |
| Purchase History | OPEN-TRAIN-1, LOCAL-TRAIN-1, CHINA-TRAIN-1; opening batch has two product lines |
| China Batch / Landed Cost | RMB 1,000, rate 40, PKR unit 40,000, carry 2,000, landed 42,000, line total 168,000, remaining 3 pieces |
| Period Profit | Sales before returns 275,000; returns 50,000; net sales 225,000; COGS 180,000; gross profit 45,000; expenses 12,000; discounts 4,000; profit after expenses 29,000 |
| Returns | One saved return against PR-000002, returned value 50,000, reversed cost 42,000 |
| Cash / Bank Period Summary | Cash: opening 500,000, money in 90,000, money out 150,000, closing 440,000. Bank: opening 300,000, money in 221,000, money out 209,000, closing 312,000 |

The account openings were dated 30 September so they appear in the Opening column for 1 October. If you put openings on the report's start date, the report classifies them within that period's money movements instead.

On a statement report, type a name and choose the matching dropdown result; simply typing unmatched text does not select a contact. Outstanding balances use To as their cutoff. Daily/monthly sales count sold pieces before returns and show return value separately.

## 24. Search, inspect, print and export

Try `a55`, `navy`, `note14black` in Stock & Products; `LOCAL-TRAIN-1` in Purchases; `PR-000002` or `Ali` in Sales. Check the From/To filters if a date-based list looks empty. Use product/contact/batch search on the report screens that offer it.

Select Samsung → **Product details**. Check the opening lot cost 40,000 and local lot cost 43,000, remaining pieces and original sales. Select an invoice → **View / Print → Save PDF**; save as `Practice-PR-000002.pdf`. Try Print / Preview; Cancel is enough if you do not want to print paper.

Open a purchase batch → **Print / PDF**. Open Ali/China account → **Print statement**. In Reports choose **Export CSV**, save e.g. `Practice-Stock.csv`, then open it in Excel if desired. The CSV is a report export, not a data import. Choose **Print / PDF** to save a report PDF too.

Invoices keep original Paid at sale and Credit at sale. Bills / balances and statements show later payments/current dues. An edited contact/product display name does not rewrite old snapshots.

## 25. Undo a mistaken entry

Start from the completed-day backup. Add an Expense: date 1 October, description `Mistaken learning expense`, amount **1,000**, Cash. Cash becomes **439,000** and profit after expenses **28,000**.

Click **Undo Last Entry** in the sidebar. Confirm it shows this expense and click **Undo This Entry**. No reason typing is required. Cash returns to **440,000**, profit to **29,000**. In Expenses the original still exists with a void timestamp. The app retains correction history.

For an older specific record use the relevant list's **Undo selected entry**, **Void** or **Correct payment** button. Customer/supplier account detail → Payments/Balance adjustments also has **Correct selected entry**. Posted invoice receipts are corrected with their original invoice, not independently through payment correction.

Unsaved text can use normal text-field Undo/Ctrl+Z; Cancel closes an unsaved entry. For an extra unsaved product line select it → **Remove selected line**. If you chose the wrong purchase type, remove all lines or Cancel before choosing a new type. Undo Last Entry covers saved business transactions, not shop settings or product/contact edits.

## 26. Learn dependency protection and fully paid local purchasing

Restore CompletedDay first. Buy one Practice Used Phone at **18,000**, Local purchase, reference `UNDO-LOCAL-1`, supplier blank, record payment **18,000 from Cash**. A fully paid purchase needs no supplier. Sell that phone to a walk-in for **22,000**, fully paid Cash.

Try selecting UNDO-LOCAL-1 → Undo selected entry. The app must block reversal because an active sale uses its stock. Undo the new 22,000 sale first, then undo the 18,000 purchase. Stock and money return to the completed-day baseline. The sale and purchase remain visibly Voided.

Later independent on-account payments are not automatically undone with a purchase/sale; they may become advances until a replacement bill is entered. Active returns must be corrected before their original invoice can be undone.

## 27. Customer and supplier advances

Restore CompletedDay. Receive **10,000 into Practice Bank** from Ali with no new sale. Ali balance **−10,000** means the shop holds customer credit; it is not extra sales profit. Review and undo this payment to return Ali to zero.

Pay China Supply **40,000 from Practice Bank** while its debt is only 30,000. Supplier balance becomes **−10,000**, an advance held by the supplier. Undo this payment to return the payable to 30,000. Future bills use advances through the account settlement view; do not enter advances as another sale/expense.

For an advance already held before the software start, the Opening balance dialog's direction checkbox records the negative balance without inventing a current-day cash movement. Use this only for an agreed real opening position.

## 28. One contact with both roles

Restore CompletedDay. Add `Bilal Trade`. Enable **Contact details, roles and availability** and tick both Customer and Supplier. It appears in both lists.

From Customers, record an opening customer debt of **5,000** on 30 September. From Suppliers, record an opening supplier debt of **7,000** on the same date. Receive **2,000 Cash** from Bilal, and pay Bilal **3,000 from Practice Bank** on 1 October.

Expected: Bilal customer receivable **3,000**, supplier payable **4,000**. These do not automatically net to a single 1,000 balance. Restore CompletedDay before the next exercise.

## 29. Manual balance adjustments

Restore CompletedDay. On Ali's account, date 1 October, enter **Add to balance 2,000**; owed becomes 2,000. Enter **Reduce balance 500**; owed becomes 1,500. Enter **Agreed discount 500**; owed becomes 1,000, and profit after expenses becomes **28,500**. No reason entry is required. Cash/Bank do not change because these are not actual receipts.

On China Supply enter **Add to balance 1,000**, then **Reduce balance 1,000**. Supplier balance moves 30,000 → 31,000 → 30,000. There is no supplier Agreed discount option that silently changes posted purchase/stock costs.

Use manual adjustments only for documented corrections/agreements. Normal new sales, supplier bills and payments should use their own entry screens. Restore CompletedDay afterward.

## 30. Rate changes and per-line overrides

Restore CompletedDay. Add an exchange rate of **41** on 1 October. Open CHINA-TRAIN-1: its rate remains **40**, landed cost **42,000**; old stock/profit never changes just because the suggested rate changed.

New China purchase, supplier China Supply, reference `FX-TRAIN-2`, default rate **41**, Xiaomi Qty **1**, RMB price **1,000**, no carry, no payment. Expected new unit cost **41,000**. Supplier debt becomes **71,000**, total stock **6 / 253,000**. Undo this new purchase or restore CompletedDay.

For a line-override exercise start again from CompletedDay, default rate **41**, same RMB price/quantity. Before adding the product choose carry currency **PKR** for this exercise. In the actual product row set rate **41.5**, enable carry and enter whole-stack carry **1,000** for the one-phone stack; leave supplier-billed carry unchecked and record no payment. The line cost becomes **41,500 + 1,000 = 42,500**, supplier debt increases by **41,500**, and external carry due is **1,000**. Changing the header default after a line has been added does not automatically rewrite that line; check the row itself. Restore CompletedDay afterward.

## 31. Returns without a refund and walk-in full refunds

Restore CompletedDay. Select PR-000003 (Ali's used-phone credit sale) → Return one used phone; refund **0**. Since Ali was fully settled by the completed-day checkpoint, the return creates customer credit **−20,000**. Cash/Bank do not change. Stock becomes **6 / 227,000**; the used phone comes back at original cost 15,000. Restore CompletedDay.

Select PR-000001 (walk-in Samsung sale) → Return one Samsung. The app requires the full **50,000** refund; choose Cash. Expected stock **6 / 252,000**, Cash **390,000**. There is no named walk-in account to hold unpaid refund credit, so a walk-in return needs a full refund. Restore CompletedDay.

To undo a return itself, use Undo Last Entry if it is the most recent active transaction, or Reports → Returns → select the record → **Undo selected return**. Later stock use can block reversal; correct those dependents first. Do not treat damaged stock as a normal saleable return.

## 32. Edit product/contact/account details and availability

Restore CompletedDay. Edit Samsung's product name to `Samsung Galaxy A55 8/256 Navy — practice edit`, add an alias `navypractice`, save and search it. Open PR-000001: its original printed product description stays as originally saved. Edit the name back, or restore CompletedDay.

Untick Active product and save. The stock list still keeps its stock/history, but it is unavailable for new entries in the product picker. Reactivate it. Do not create another product just to hide an old one.

Edit Ali's phone/address/notes; use your own fictional labels and leave sensitive real data out. Existing invoice customer snapshots remain as saved. Untick Active contact to stop new entries, then reactivate. Keep a historical Customer/Supplier role if it already has that role's transactions; the app blocks removing a used role.

Edit Practice Bank's name to `Training Bank`, inspect Account activity, then restore CompletedDay. Once transactions exist, its opening amount/date are protected; editing the name does not rewrite balances. Inactive accounts are unavailable for new payments but history is retained. Keep at least one active payment account. Account type is fixed when editing an existing account.

## 33. Practice safe validation failures

Restore CompletedDay and try each in an unsaved form. Cancel after the expected error:

| Attempt | Expected behaviour |
|---|---|
| Sell 99 Samsung phones | Insufficient stock; no sale/payment posted |
| Credit sale with no selected customer | Requires a customer; no entry posted |
| A 50,000 sale with a 60,000 receipt | Rejects overpayment |
| Leave a product's purchase/selling price blank | Requires a price before Save |
| Unpaid local purchase with no supplier | Requires a supplier in the entry screen |
| Transfer Cash to the same Cash account | Requires different accounts |
| Reuse LOCAL-TRAIN-1 as a batch reference | Duplicate reference blocked; use a new reference |
| Return more units than the original unreturned quantity | Quantity control prevents excess return |
| Put stock activity before the product's later saved stock date | Chronology protection blocks it; correct in order |
| Review Undo Last Entry | No reason input; purchase undo still requires owner credentials |
| Restore/reset with wrong owner password | No replacement; five bad attempts require a one-minute wait |
| Reset without typing RESET exactly | No records cleared |

Check that stock, balances and active invoices still match CompletedDay. A date filter can hide a saved entry; check the date range before assuming Save failed or entering it again.

## 34. Practice a catalogue update

Restore CompletedDay. In this practice shop only, choose **Settings → Mobile Catalogue → Import Catalogue Update** and select the supplied `Sample-Catalogue-Update.json` from this folder. It contains one clearly fictional reference: **Practice Brand / Learning Phone**, version **2026.10.01.1**.

Search `learningphone` in Mobile Catalogue. Finding the reference does not add stock, change phone costs or modify invoices. Try Create Shop Product from it if desired: that product starts at zero quantity until you purchase/open stock. If you import the same package again, the app says that version is already installed/older.

Restore CompletedDay to remove the exercise update/product and recover that backup's catalogue. Full reset instead preserves the current catalogue, including updates; that difference is intentional. On a real shop only use trusted, properly versioned update packages. Excel workbooks are not a catalogue update or business import.

## 35. Change the practice owner's password

Open **Settings → Owner & Reset → Change owner password**. Enter the current practice password, choose your own new password and confirm it. A mismatched confirmation or incorrect current password should stop the change.

Keep the new credentials: restoring CleanSetup, Openings or CompletedDay does not put the old password back. Owner protection is kept separately from replaceable business backups. Do not perform this exercise with the client's actual owner credentials.

## 36. Full reset and recovery

Start from CompletedDay. Open **Settings → Owner & Reset → Reset All Business Data**. Review the counts, enter the current practice owner credentials, type `RESET`, and click **Back Up and Reset All Data**.

Expected: no shop products/contacts/purchases/sales/payments, zero stock and zero money/openings, invoice sequence 1. Shop details, account names, reference catalogue and owner credentials stay. The success dialog shows a safety `.mdbackup` path; copy or note that path. The automatic backup must succeed or nothing is cleared.

Open **Settings → Backup & Restore → Restore Backup**, select that safety backup, confirm replacement and enter the current owner credentials. Expected: the completed-day stock **5 / 212,000**, Cash **440,000**, Bank **312,000**, Ali **0**, China payable **30,000** return. Restore also saves a safety backup of the state it replaces.

To start completely empty again, restore the backup inside `01-CleanSetup`. To repeat the day with initial balances/products ready, restore `02-Openings`. To repeat just an extra exercise, restore `03-CompletedDay`. Make sure you select the backup file itself inside the chosen folder.

## 37. Learn month-end continuity

With the completed-day records restored, choose a report range in **November 2026**. There are no November sales in this lesson, so the sales view is empty. Current Stock still shows **5 pieces**, account balances continue, and supplier outstanding as of November still includes China's **30,000** debt.

That is the expected behaviour: a new month starts with earlier stock, money and unpaid balances. Do not reset the whole business to make a monthly report empty. Change report dates.

## 38. A normal day's operating order

1. Open the normal shop for real work or the clearly separate practice shortcut for training.
2. Check today's date, Cash/Bank, stock and outstanding debts.
3. Record actual new purchases and actual supplier/transport payments.
4. Save sales with the real quantity, price, customer when needed, and actual payment account/amount.
5. Record later customer collections and supplier payments separately.
6. Record saleable returns/refunds, genuine operating expenses and account transfers.
7. Correct mistakes with an audited undo and replacement entry.
8. Check Stock, customer/supplier statements, Cash/Bank and Period Profit.
9. Export/print useful reports and save a dated backup, preferably also on another disk/USB.

Do not overwrite openings during daily work, double-count a carry expense, treat a transfer/collection as a sale, or clear business history merely because a new month starts.

## 39. Quick self-check

You understand the workflow when you can explain why a catalogue product has no stock; why opening stock does not spend money; why a credit sale can have profit before collection; why a collection does not add sales; why supplier payment does not subtract profit again; why FIFO used 40,000 and 43,000 on the same Samsung invoice; why returns recover original cost; why negative balances mean advances; why month-end retains debts; and why reset is different from undo.

Keep the verified results file beside this workbook if you want to compare every checkpoint. If a figure differs, stop at that stage and check dates, quantities, carry billing, payment account, selected contact and whether a line's actual rate differs from the header default. Restore the appropriate practice checkpoint and repeat; do not invent an adjustment merely to force the expected answer.
