import json
import sqlite3

import pytest

from mobile_desk.services.purchase_returns import PurchaseReturnService
from mobile_desk.values import BusinessError


OWNER = 'owner'
PASSWORD = 'Returns-Only-2026'
DAY = '2026-10-01'


@pytest.fixture
def returns(shop):
    shop.security.set_password(OWNER, PASSWORD, PASSWORD)
    return PurchaseReturnService(shop.db, shop.security)


def buy(shop, *, qty=10, paid='0', price='100', supplier=True, carry='0',
        carrier_paid='0', billed=False, pending=False):
    kwargs = dict(supplier_id=shop.supplier if supplier else None,
                  payments=[dict(account_id=shop.cash, amount=paid)] if paid != '0' else [],
                  default_carry=carry, carry_billed_to_supplier=billed,
                  carry_payment=carrier_paid,
                  carry_account_id=shop.cash if carrier_paid != '0' else None)
    if pending:
        kwargs['received'] = False
    return shop.purchases.post(DAY, [dict(product_id=shop.product, quantity=qty, unit_price=price)], **kwargs)


def line(shop, purchase, qty):
    item = shop.db.one('SELECT id FROM purchase_items WHERE purchase_batch_id=?', (purchase,))
    return [dict(purchase_item_id=item['id'], quantity=qty)]


def post(returns, shop, purchase, qty, **kwargs):
    return returns.post(purchase, kwargs.pop('day', DAY), line(shop, purchase, qty),
                        kwargs.pop('reason', 'Shipment returned by cargo'), OWNER, PASSWORD, **kwargs)


def cash(shop):
    return next(a['balance'] for a in shop.money.accounts() if a['id'] == shop.cash)


def supplier_balance(shop):
    return shop.parties.balance(shop.supplier, role='SUPPLIER')


def test_return_requires_owner_and_preserves_everything_on_bad_auth(shop):
    purchase = buy(shop, paid='1000')
    service = PurchaseReturnService(shop.db, shop.security)
    with pytest.raises(BusinessError, match='set a password'):
        service.post(purchase, DAY, line(shop, purchase, 10), 'Cargo lost', OWNER, PASSWORD)
    shop.security.set_password(OWNER, PASSWORD, PASSWORD)
    for username, password in [('employee', PASSWORD), (OWNER, 'wrong')]:
        with pytest.raises(BusinessError, match='Incorrect owner'):
            service.post(purchase, DAY, line(shop, purchase, 10), 'Cargo lost', username, password)
    assert shop.stock.totals()['quantity'] == 10
    assert cash(shop) == -100000
    assert shop.db.one('SELECT COUNT(*) n FROM purchase_returns')['n'] == 0


def test_unpaid_purchase_return_reduces_bill_without_inventing_cash(shop, returns):
    purchase = buy(shop)
    assert supplier_balance(shop) == 100000
    with pytest.raises(BusinessError, match='Unpaid bills'):
        post(returns, shop, purchase, 10, refund_amount='1000', refund_account_id=shop.cash)
    assert shop.stock.totals()['quantity'] == 10
    assert shop.db.one('SELECT COUNT(*) n FROM purchase_returns')['n'] == 0
    identity = post(returns, shop, purchase, 10)
    assert shop.stock.totals() == dict(quantity=0, value=0)
    assert supplier_balance(shop) == cash(shop) == 0
    assert returns.refund_limits(identity)['supplier'] == 0
    assert returns.details(identity)['header']['supplier_credit'] == 100000
    assert shop.purchases.details(purchase)[0]['status'] == 'POSTED'
    assert shop.purchases.details(purchase)[0]['shipment_status'] == 'RETURNED'


def test_paid_full_return_receives_only_confirmed_refund_and_keeps_originals(shop, returns):
    purchase = buy(shop, paid='1000')
    original = shop.db.one('SELECT * FROM purchase_items WHERE purchase_batch_id=?', (purchase,))
    identity = post(returns, shop, purchase, 10, refund_amount='1000', refund_account_id=shop.cash)
    assert cash(shop) == supplier_balance(shop) == 0
    assert shop.stock.totals() == dict(quantity=0, value=0)
    assert shop.db.one('SELECT * FROM purchase_items WHERE id=?', (original['id'],)) == original
    assert shop.db.one('SELECT voided_at FROM payments WHERE purchase_batch_id=?', (purchase,))['voided_at'] is None
    detail = returns.details(identity)
    assert detail['refunds'][0]['amount'] == 100000
    assert detail['header']['owner_username'] == OWNER
    logged = shop.db.one("SELECT reason FROM audit_log WHERE entity='purchase_return' AND entity_id=?", (str(identity),))
    evidence = json.loads(logged['reason'])
    assert evidence['owner_username'] == OWNER
    assert evidence['lines'][0]['quantity'] == 10
    assert evidence['confirmed_refund'] == 100000
    assert evidence['reason'] == 'Shipment returned by cargo'


def test_partial_returns_and_refunds_never_repeat_quantity_or_money(shop, returns):
    purchase = buy(shop, paid='1000')
    first = post(returns, shop, purchase, 4, refund_amount='400', refund_account_id=shop.cash)
    assert cash(shop) == -60000
    assert shop.stock.totals() == dict(quantity=6, value=60000)
    assert returns.preview(purchase)['lines'][0]['returnable_quantity'] == 6
    with pytest.raises(BusinessError, match='unreturned quantity'):
        post(returns, shop, purchase, 7)
    second = post(returns, shop, purchase, 6)
    assert supplier_balance(shop) == -60000
    assert cash(shop) == -60000
    with pytest.raises(BusinessError, match='exceeds'):
        returns.confirm_refund(first, DAY, shop.cash, '1', OWNER, PASSWORD)
    returns.confirm_refund(second, DAY, shop.bank, '200', OWNER, PASSWORD)
    returns.confirm_refund(second, DAY, shop.cash, '400', OWNER, PASSWORD)
    assert supplier_balance(shop) == 0
    assert cash(shop) == -20000
    with pytest.raises(BusinessError, match='exceeds'):
        returns.confirm_refund(second, DAY, shop.cash, '0.01', OWNER, PASSWORD)
    assert len(returns.list(purchase_id=purchase)) == 2
    assert len(returns.refunds(purchase_id=purchase)) == 3


def test_return_and_refund_double_submit_keys_are_atomic(shop, returns):
    purchase = buy(shop, paid='1000')
    first = post(returns, shop, purchase, 10, key='return-once')
    assert post(returns, shop, purchase, 10, key='return-once') == first
    refund = returns.confirm_refund(first, DAY, shop.cash, '1000', OWNER, PASSWORD, key='refund-once')
    assert returns.confirm_refund(first, DAY, shop.cash, '1000', OWNER, PASSWORD, key='refund-once') == refund
    with pytest.raises(BusinessError, match='different details'):
        returns.confirm_refund(first, DAY, shop.cash, '999', OWNER, PASSWORD, key='refund-once')
    assert cash(shop) == 0
    assert shop.db.one('SELECT COUNT(*) n FROM purchase_returns')['n'] == 1
    assert shop.db.one('SELECT COUNT(*) n FROM purchase_refunds')['n'] == 1


def test_return_does_not_use_sold_stock_and_checks_chronology(shop, returns):
    purchase = buy(shop)
    shop.sales.post('2026-10-03', [dict(product_id=shop.product, quantity=3, selling_rate='130')],
                    customer_id=shop.customer)
    with pytest.raises(BusinessError, match='stock activity'):
        post(returns, shop, purchase, 1, day='2026-10-02')
    with pytest.raises(BusinessError, match='sold or used'):
        post(returns, shop, purchase, 8, day='2026-10-04')
    identity = post(returns, shop, purchase, 7, day='2026-10-04')
    assert returns.details(identity)['header']['stock_cost'] == 70000
    assert shop.stock.totals()['quantity'] == 0
    assert shop.purchases.details(purchase)[0]['shipment_status'] == 'RECEIVED'


def test_pending_partial_and_full_cancellation_never_creates_stock_movements(shop, returns):
    purchase = buy(shop, paid='1000', pending=True)
    assert shop.stock.totals()['quantity'] == 0
    first = post(returns, shop, purchase, 4)
    assert returns.details(first)['header']['kind'] == 'CANCELLATION'
    assert shop.purchases.details(purchase)[0]['shipment_status'] == 'IN_TRANSIT'
    post(returns, shop, purchase, 6, refund_amount='600', refund_account_id=shop.cash)
    returns.confirm_refund(first, DAY, shop.cash, '400', OWNER, PASSWORD)
    assert shop.purchases.details(purchase)[0]['shipment_status'] == 'CANCELLED'
    assert shop.stock.totals()['quantity'] == 0
    assert shop.db.one('SELECT COUNT(*) n FROM stock_movements')['n'] == 0
    assert cash(shop) == supplier_balance(shop) == 0


def test_partially_cancelled_shipment_receives_only_uncancelled_phones(shop, returns):
    purchase = buy(shop, pending=True)
    post(returns, shop, purchase, 4, day='2026-10-03')
    with pytest.raises(BusinessError, match='date|cancellation'):
        shop.purchases.receive(purchase, '2026-10-02')
    shop.purchases.receive(purchase, '2026-10-04')
    assert shop.stock.totals() == dict(quantity=6, value=60000)
    assert returns.preview(purchase)['lines'][0]['returnable_quantity'] == 6
    with pytest.raises(BusinessError, match='arrival date'):
        post(returns, shop, purchase, 1, day='2026-10-03')
    post(returns, shop, purchase, 6, day='2026-10-04')
    assert shop.stock.totals()['quantity'] == 0
    assert shop.purchases.details(purchase)[0]['shipment_status'] == 'RETURNED'
    assert supplier_balance(shop) == 0


def test_confirming_refund_also_requires_owner_authentication(shop, returns):
    purchase = buy(shop, paid='1000')
    identity = post(returns, shop, purchase, 10)
    with pytest.raises(BusinessError, match='Incorrect owner'):
        returns.confirm_refund(identity, DAY, shop.cash, '1000', OWNER, 'wrong-password')
    assert returns.refunds(identity) == []
    assert cash(shop) == -100000
    assert supplier_balance(shop) == -100000


def test_separate_carry_refund_is_limited_to_actual_carrier_payment(shop, returns):
    purchase = buy(shop, paid='1000', carry='10', carrier_paid='100')
    identity = post(returns, shop, purchase, 4, refund_amount='400', refund_account_id=shop.cash)
    limits = returns.refund_limits(identity)
    assert limits['supplier'] == 0
    assert limits['carrier'] == 4000
    assert shop.stock.totals() == dict(quantity=6, value=66000)
    with pytest.raises(BusinessError, match='Carrier refund exceeds'):
        returns.confirm_refund(identity, DAY, shop.cash, '40.01', OWNER, PASSWORD, payer='CARRIER')
    returns.confirm_refund(identity, DAY, shop.cash, '40', OWNER, PASSWORD, payer='CARRIER')
    assert cash(shop) == -66000
    assert supplier_balance(shop) == 0
    assert returns.refund_limits(identity)['carrier'] == 0


def test_unpaid_external_carry_is_not_refundable_cash(shop, returns):
    purchase = buy(shop, paid='1000', carry='10')
    identity = post(returns, shop, purchase, 10)
    assert returns.refund_limits(identity)['external_carry_credit_remaining'] == 10000
    assert returns.refund_limits(identity)['carrier'] == 0
    with pytest.raises(BusinessError, match='Carrier refund exceeds'):
        returns.confirm_refund(identity, DAY, shop.cash, '100', OWNER, PASSWORD, payer='CARRIER')


def test_supplier_billed_carry_uses_supplier_credit_not_carrier_credit(shop, returns):
    purchase = buy(shop, paid='1100', carry='10', billed=True)
    identity = post(returns, shop, purchase, 4, refund_amount='440', refund_account_id=shop.cash)
    assert returns.details(identity)['header']['supplier_credit'] == 44000
    assert returns.refund_limits(identity)['carrier'] == 0
    assert supplier_balance(shop) == 0


def test_anonymous_purchase_refund_caps_at_actual_paid_amount(shop, returns):
    purchase = buy(shop, paid='400', supplier=False)
    identity = post(returns, shop, purchase, 10)
    assert returns.refund_limits(identity)['supplier'] == 40000
    with pytest.raises(BusinessError, match='exceeds'):
        returns.confirm_refund(identity, DAY, shop.cash, '1000', OWNER, PASSWORD)
    returns.confirm_refund(identity, DAY, shop.cash, '400', OWNER, PASSWORD)
    assert cash(shop) == 0
    assert returns.refund_limits(identity)['supplier'] == 0


def test_supplier_credit_already_used_for_other_purchase_cannot_be_refunded_again(shop, returns):
    purchase = buy(shop, paid='1000')
    identity = post(returns, shop, purchase, 10)
    buy(shop, qty=6)
    assert supplier_balance(shop) == -40000
    assert returns.refund_limits(identity)['supplier'] == 40000
    with pytest.raises(BusinessError, match='exceeds'):
        returns.confirm_refund(identity, DAY, shop.cash, '1000', OWNER, PASSWORD)
    returns.confirm_refund(identity, DAY, shop.cash, '400', OWNER, PASSWORD)
    assert supplier_balance(shop) == 0


def test_refund_cannot_precede_return_or_spend_future_supplier_credit(shop, returns):
    purchase = buy(shop)
    identity = post(returns, shop, purchase, 10, day='2026-10-03')
    with pytest.raises(BusinessError, match='cannot precede'):
        returns.confirm_refund(identity, DAY, shop.cash, '1', OWNER, PASSWORD)
    shop.money.pay_supplier(shop.supplier, '2026-10-05', shop.cash, '1000')
    assert returns.refund_limits(identity, '2026-10-03')['supplier'] == 0
    with pytest.raises(BusinessError, match='exceeds'):
        returns.confirm_refund(identity, '2026-10-03', shop.cash, '1000', OWNER, PASSWORD)
    returns.confirm_refund(identity, '2026-10-05', shop.cash, '1000', OWNER, PASSWORD)
    assert cash(shop) == 0


def test_return_validates_selected_lines_dates_and_opening_stock(shop, returns):
    purchase = buy(shop)
    other = buy(shop, qty=1)
    for selected, reason, day, match in [
        ([], 'reason', DAY, 'at least one'),
        (line(shop, other, 1), 'reason', DAY, 'belong'),
        (line(shop, purchase, 1)*2, 'reason', DAY, 'once'),
        (line(shop, purchase, 1), 'reason', '2026-09-30', 'precede'),
    ]:
        with pytest.raises(BusinessError, match=match):
            returns.post(purchase, day, selected, reason, OWNER, PASSWORD)
    opening = shop.purchases.post(DAY, [dict(product_id=shop.product, quantity=1, unit_price='100')],
                                 purchase_type='OPENING')
    with pytest.raises(BusinessError, match='Opening stock'):
        post(returns, shop, opening, 1)
    assert shop.db.one('SELECT COUNT(*) n FROM purchase_returns')['n'] == 0


def test_return_and_refund_history_cannot_be_changed_or_deleted(shop, returns):
    purchase = buy(shop, paid='1000')
    identity = post(returns, shop, purchase, 10, refund_amount='1000', refund_account_id=shop.cash)
    for sql in [
        'UPDATE purchase_returns SET supplier_credit=0',
        'UPDATE purchase_return_items SET quantity=1',
        'UPDATE purchase_refunds SET amount=1',
        'DELETE FROM purchase_refunds',
        'DELETE FROM purchase_return_items',
        'DELETE FROM purchase_returns',
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            with shop.db.connect(write=True) as c:
                c.execute(sql)
    assert returns.details(identity)['header']['supplier_credit'] == 100000
    assert cash(shop) == 0
