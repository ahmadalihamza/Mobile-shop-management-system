# Practice the China import workflow — Mobile Desk 1.6.0

Use the separate practice shop, never the client's real records. Back up that practice shop first. The examples below were verified through the actual Windows forms with fictional prices, contacts and dates. Start in an empty practice shop with Cash and a bank account, a product named Huawei P30 Pro, and one supplier named China training supplier. Set your own owner credentials in Settings → Owner & Reset.

## 1. Buy the first stack

New Purchase, date 1 October 2026. Select China import (RMB), the saved training supplier and reference IMPORT-STACK-1. Shipment: Stock has arrived. Set rate 40, enable carry, and select Additional costs are included in the supplier bill. Add Huawei P30 Pro, 6 pieces, RMB 500 per phone, and **RMB 150 total carry for the whole stack**. Record a full payment from Cash.

Expected: (6 × 500 + 150) × 40 = PKR 126,000. Carry is charged once: PKR 6,000 for the stack, or PKR 1,000 allocated to each phone. Landed cost is PKR 21,000 per phone. Available stock is 6 pieces / PKR 126,000. Cash changed by −126,000.

## 2. Enter a second shipment before arrival

Open New Purchase again. China import and the same supplier should already be selected. Date 2 October, reference IMPORT-STACK-2, Shipment: Awaiting arrival. Add the same phone, 10 pieces at RMB 600 each, rate 40 and **RMB 525 carry for that whole stack**. Include carry in the supplier bill and record full payment of PKR 261,000 from the bank.

Expected: (10 × 600 + 525) × 40 = PKR 261,000. Total acquired cost across the 16 phones is PKR 387,000. Stock & Products shows **Average Purchase Price PKR 24,187.50**. Physically available stock remains 6 pieces / PKR 126,000 because the other 10 have not arrived. Adding an awaiting-arrival purchase never makes it saleable.

## 3. Cancel four incoming phones

Select IMPORT-STACK-2 → Return / Cancel. Date 3 October. Change Return now from 10 to 4. There is no reason field to fill in. Leave Money has actually been received back unchecked. Enter your owner credentials, review the reference, quantity and credit, tick the confirmation and finalize.

Expected: supplier credit PKR 104,400. Available stock is still 6 pieces. Cash / Bank has not increased. Six uncancelled phones remain on order. The net acquisition average is now PKR 23,550 across 12 phones.

## 4. Confirm the refund in two instalments

Select that purchase → Returns / refunds → select its cancellation → Confirm refund. Date 4 October, actual amount PKR 40,000, received into the bank, payer Supplier. Authenticate and confirm actual receipt. Repeat on 5 October for PKR 64,400. Total refunded: PKR 104,400. The program cannot refund it twice or treat an unpaid/unconfirmed claim as cash.

## 5. Receive the remaining phones

Select IMPORT-STACK-2 → Mark received. Date 6 October. Confirm the phones physically arrived and save. Expected available stock: 12 pieces / PKR 282,600. Only the six uncancelled incoming phones were added. A second receipt attempt is blocked.

## 6. Return part of the first arrived stack

Select IMPORT-STACK-1 → Return / Cancel. Date 7 October, Return now 2. If the supplier has actually refunded PKR 42,000, check the received-money option, enter that amount and choose Cash. Enter owner credentials, review, confirm and finalize.

Expected: available stock 10 pieces / PKR 240,600; Average Purchase Price PKR 24,060. Total confirmed refunds are PKR 146,400. Across Cash and bank, net money paid is PKR 240,600. Supplier balance is zero. Original purchases, payments, automatic action descriptions, owners and refund dates remain visible in history.

## 7. Try a charge that does not divide evenly

In a separate practice exercise, enter 6 phones at RMB 1,000 each with a whole-stack carry charge of RMB 1 at rate 40. Exact total: PKR 240,040. The PKR 40 carry cannot divide equally to the paisa across six phones; the app preserves the whole PKR 40 by allocating two phones PKR 6.66 and four phones PKR 6.67 carry. You still see one stack in the report and return form. Partial returns use those original costs.

## 8. Check the safeguards

An incorrect owner password must save nothing. An awaiting-arrival phone cannot be sold. A partial supplier return cannot exceed unsold available pieces. Finalized return/refund records cannot be silently deleted. For actual refunds that have not arrived, leave cash unchanged and confirm them later. Restore the practice backup to repeat these exercises.
