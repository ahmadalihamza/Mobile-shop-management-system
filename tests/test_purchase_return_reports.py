"""Purchase credits, actual refunds, stock costs and period reports reconcile."""
import pytest

from mobile_desk.values import BusinessError, money


OWNER = 'practice-owner'
PASSWORD = 'Purchase returns test 26!'


def configure_owner(shop):
    shop.security.set_password(OWNER, PASSWORD, PASSWORD)


def buy(shop, day, qty, price='1000', *, paid='0', carry='0', carry_paid='0', **kwargs):
    return shop.purchases.post(
        day, [dict(product_id=shop.product, quantity=qty, unit_price=price, carry=carry)],
        supplier_id=shop.supplier,
        payments=[dict(account_id=shop.cash, amount=paid)] if paid != '0' else [],
        carry_payment=carry_paid, carry_account_id=shop.cash, **kwargs)


def return_stock(shop, purchase, day, qty, **kwargs):
    item = shop.purchases.details(purchase)[1][0]
    return shop.purchase_returns.post(
        purchase, day, [dict(purchase_item_id=item['id'], quantity=qty)],
        'Shipment returned to the supplier', OWNER, PASSWORD, **kwargs)


def test_supplier_return_credit_settles_its_original_invoice(shop):
    configure_owner(shop)
    first = buy(shop, '2026-09-01', 2, paid='1500')
    second = buy(shop, '2026-09-02', 1)
    before = shop.parties.documents(shop.supplier, '2026-09-02', role='SUPPLIER')
    assert [r['outstanding'] for r in before] == [money('500'), money('1000')]

    return_stock(shop, second, '2026-09-03', 1)
    after = shop.parties.documents(shop.supplier, role='SUPPLIER')
    assert len(after) == 2
    assert [r['reference'] for r in after] == [shop.purchases.details(p)[0]['reference'] for p in (first, second)]
    assert [r['outstanding'] for r in after] == [money('500'), 0]
    assert sum(r['outstanding'] for r in after) == shop.parties.balance(shop.supplier, role='SUPPLIER')
    assert shop.parties.documents(shop.supplier, '2026-09-02', role='SUPPLIER') == before
    assert shop.reports.supplier_outstanding('2026-09-02')[0]['balance'] == money('1500')
    assert shop.reports.supplier_outstanding('2026-09-03')[0]['balance'] == money('500')


def test_supplier_refund_stays_on_original_document_and_unused_credit_pays_next_bill(shop):
    configure_owner(shop)
    first = buy(shop, '2026-09-01', 2, paid='2000')
    returned = return_stock(shop, first, '2026-09-02', 1)
    cash_before = shop.money.accounts()[0]['balance']
    assert cash_before == -money('2000')  # A return alone does not invent cash.
    shop.purchase_returns.confirm_refund(returned, '2026-09-03', shop.cash, '500', OWNER, PASSWORD)
    buy(shop, '2026-09-04', 1)

    documents = shop.parties.documents(shop.supplier, role='SUPPLIER')
    assert len(documents) == 2  # No separate positive refund/invoice bucket.
    assert [r['outstanding'] for r in documents] == [0, money('500')]
    assert shop.parties.balance(shop.supplier, role='SUPPLIER') == money('500')
    assert shop.money.accounts()[0]['balance'] == cash_before + money('500')
    assert shop.parties.balance(shop.customer) == 0
    assert [r['balance'] for r in shop.parties.statement(shop.supplier, role='SUPPLIER')][-1] == money('500')


def test_rmb_carry_return_and_later_refunds_reconcile_profit_cash_and_fifo(shop):
    configure_owner(shop)
    purchase = buy(shop, '2026-09-01', 4, paid='160000', carry='25', carry_paid='4000',
                   purchase_type='CHINA_IMPORT', default_rate='40', carry_currency='CNY')
    returned = return_stock(shop, purchase, '2026-09-03', 1)
    assert shop.parties.balance(shop.supplier, role='SUPPLIER') == -money('40000')
    assert shop.money.accounts()[0]['balance'] == -money('164000')
    assert shop.stock.totals()['value'] == money('123000')
    before_refund = shop.reports.period_profit('2026-09-01', '2026-09-30')
    assert before_refund['purchase_return_cost_loss'] == money('1000')
    assert before_refund['profit_after_expenses'] == -money('1000')
    assert before_refund['gross_profit'] == 0

    shop.purchase_returns.confirm_refund(returned, '2026-09-04', shop.cash, '40000', OWNER, PASSWORD)
    assert shop.reports.period_profit('2026-09-01', '2026-09-30') == before_refund
    shop.purchase_returns.confirm_refund(returned, '2026-10-01', shop.bank, '600', OWNER, PASSWORD, payer='CARRIER')
    assert shop.reports.period_profit('2026-09-01', '2026-09-30') == before_refund
    october = shop.reports.period_profit('2026-10-01', '2026-10-31')
    assert october['carry_refunds_received'] == october['profit_after_expenses'] == money('600')
    assert october['purchase_return_cost_loss'] == 0

    shop.sales.post('2026-09-05', [dict(product_id=shop.product, quantity=1, selling_rate='50000')],
                    payments=[dict(account_id=shop.cash, amount='50000')])
    september = shop.reports.period_profit('2026-09-01', '2026-09-30')
    assert september['cogs'] == money('41000')
    assert september['gross_profit'] == money('9000')
    assert september['profit_after_expenses'] == money('8000')
    assert shop.reports.period_profit('1900-01-01', '9999-12-31')['profit_after_expenses'] == money('8600')
    assert shop.stock.totals()['value'] == money('82000')

    history = shop.reports.purchase_history('2026-09-01', '2026-09-30', china=True)
    assert len(history) == 1
    row = history[0]
    assert (row['quantity'], row['returned_quantity'], row['net_quantity'], row['remaining_quantity']) == (4, 1, 3, 2)
    assert row['line_total_cost'] == money('164000')
    assert row['returned_stock_cost'] == money('41000')
    assert row['net_stock_cost'] == money('123000')
    assert row['supplier_credit'] == money('40000')
    assert row['carry_currency'] == 'CNY' and row['foreign_carry_per_unit'] == '25'
    assert row['exchange_rate_snapshot'] == '40'
    cash = {r['id']: r for r in shop.reports.cash_summary('2026-09-01', '2026-09-30')}
    assert (cash[shop.cash]['received'], cash[shop.cash]['paid_out'], cash[shop.cash]['closing']) == (money('90000'), money('164000'), -money('74000'))
    bank = {r['id']: r for r in shop.reports.cash_summary('2026-10-01', '2026-10-31')}[shop.bank]
    assert bank['received'] == bank['closing'] == money('600')
    kinds = {r['kind'] for r in shop.reports.recent()}
    assert {'Stock return', 'Supplier refund', 'Carry refund'} <= kinds


def test_in_transit_cancellation_keeps_original_history_and_has_no_fake_refund(shop):
    configure_owner(shop)
    purchase = buy(shop, '2026-09-01', 3, paid='1000', received=False)
    assert shop.stock.totals()['quantity'] == 0
    returned = return_stock(shop, purchase, '2026-09-02', 3)
    assert shop.parties.balance(shop.supplier, role='SUPPLIER') == -money('1000')
    assert shop.money.accounts()[0]['balance'] == -money('1000')
    history = shop.reports.purchase_history('2026-09-01', '2026-09-30')[0]
    assert history['quantity'] == history['returned_quantity'] == 3
    assert history['net_quantity'] == history['net_stock_cost'] == history['remaining_quantity'] == 0
    assert history['shipment_status'] == 'CANCELLED'
    assert shop.reports.period_profit('2026-09-01', '2026-09-30')['profit_after_expenses'] == 0
    shop.purchase_returns.confirm_refund(returned, '2026-09-03', shop.bank, '1000', OWNER, PASSWORD)
    assert sum(a['balance'] for a in shop.money.accounts()) == 0
    assert shop.reports.supplier_outstanding() == []
    assert len(shop.parties.documents(shop.supplier, role='SUPPLIER')) == 1
    assert shop.parties.documents(shop.supplier, role='SUPPLIER')[0]['outstanding'] == 0
    assert shop.purchases.details(purchase)[0]['status'] == 'POSTED'
    assert any(r['kind'] == 'Purchase cancellation' for r in shop.reports.recent())


def test_remaining_carry_payments_respect_returned_costs_and_confirmed_recoveries(shop):
    configure_owner(shop)
    purchase = buy(shop, '2026-09-01', 4, price='100', carry='10', carry_paid='10')
    returned = return_stock(shop, purchase, '2026-09-02', 2)
    with pytest.raises(BusinessError, match='remaining transport'):
        shop.money.pay_carry(purchase, '2026-09-03', shop.cash, '10.01')
    later = shop.money.pay_carry(purchase, '2026-09-03', shop.cash, '10')
    with pytest.raises(BusinessError, match='return or cancellation'):
        shop.money.void('payment', later, 'Cannot erase payment supporting return history')
    shop.purchase_returns.confirm_refund(returned, '2026-09-04', shop.bank, '20', OWNER, PASSWORD, payer='CARRIER')
    shop.money.pay_carry(purchase, '2026-09-04', shop.cash, '20')
    with pytest.raises(BusinessError, match='remaining transport'):
        shop.money.pay_carry(purchase, '2026-09-04', shop.cash, '0.01')
    return_stock(shop, purchase, '2026-09-05', 2)
    with pytest.raises(BusinessError, match='not available'):
        shop.money.pay_carry(purchase, '2026-09-05', shop.cash, '1')


def test_on_account_supplier_payment_cannot_be_erased_after_confirmed_refund(shop):
    configure_owner(shop)
    purchase = buy(shop, '2026-09-01', 2)
    payment = shop.money.pay_supplier(shop.supplier, '2026-09-01', shop.cash, '2000')
    returned = return_stock(shop, purchase, '2026-09-02', 1)
    shop.purchase_returns.confirm_refund(returned, '2026-09-03', shop.cash, '500', OWNER, PASSWORD)
    balances = [(a['id'], a['balance']) for a in shop.money.accounts()]
    with pytest.raises(BusinessError, match='confirmed refund history'):
        shop.money.void('payment', payment, 'Keep the payment supporting the refund')
    assert shop.db.one('SELECT voided_at FROM payments WHERE id=?', (payment,))['voided_at'] is None
    assert [(a['id'], a['balance']) for a in shop.money.accounts()] == balances
    assert shop.parties.balance(shop.supplier, role='SUPPLIER') == -money('500')
