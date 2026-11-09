from decimal import Decimal
import pytest
from mobile_desk.values import BusinessError, money, quantity, decimal
from mobile_desk.services.purchases import price_line


def buy(s, qty=10, rate='40000', day='2026-09-01', **kwargs):
    return s.purchases.post(day, [dict(product_id=s.product, quantity=qty, unit_price=rate)], **kwargs)


def sell(s, qty=2, rate='50000', paid='0', day='2026-09-02', **kwargs):
    return s.sales.post(day, [dict(product_id=s.product, quantity=qty, selling_rate=rate)], customer_id=s.customer, payments=[dict(account_id=s.cash, amount=paid)] if paid!='0' else [], **kwargs)


def test_china_cost_and_line_override(shop):
    identity = shop.purchases.post('2026-09-01', [dict(product_id=shop.product, quantity=3, unit_price='1000', exchange_rate='40.3', carry='4000'), dict(product_id=shop.product, quantity=2, unit_price='1000', exchange_rate='39.7')], purchase_type='CHINA_IMPORT', default_rate='41.066', default_carry='2000')
    header, lines = shop.purchases.details(identity)
    assert lines[0]['pkr_unit_purchase_cost'] == money('40300')
    assert lines[0]['landed_unit_cost'] == money('44300')
    assert lines[1]['landed_unit_cost'] == money('41700')
    assert header['total'] == money('216300')


def test_historical_rates_never_reprice(shop):
    a = shop.purchases.post('2026-09-01', [dict(product_id=shop.product, quantity=1, unit_price='1000')], purchase_type='CHINA_IMPORT', default_rate='39.8')
    b = shop.purchases.post('2026-09-02', [dict(product_id=shop.product, quantity=1, unit_price='1000')], purchase_type='CHINA_IMPORT', default_rate='41.25')
    shop.money.add_rate('2026-09-03', '99')
    assert shop.purchases.details(a)[1][0]['landed_unit_cost'] == money('39800')
    assert shop.purchases.details(b)[1][0]['landed_unit_cost'] == money('41250')


def test_fifo_spans_lots(shop):
    buy(shop, 5, '40000')
    buy(shop, 10, '45000', day='2026-09-02')
    identity = sell(shop, 8, day='2026-09-03')
    assert shop.sales.details(identity)[1][0]['cogs'] == money('335000')
    assert [r['remaining_quantity'] for r in shop.stock.lots(shop.product)] == [0, 7]
    assert shop.stock.totals() == dict(quantity=7, value=money('315000'))


def test_credit_collection_statement(shop):
    buy(shop)
    sell(shop, paid='30000')
    assert shop.parties.balance(shop.customer) == money('70000')
    shop.money.collect(shop.customer, '2026-09-03', shop.bank, '20000')
    assert shop.parties.balance(shop.customer) == money('50000')
    assert shop.parties.statement(shop.customer)[-1]['balance'] == money('50000')


def test_return_original_cost_partial_multilot(shop):
    buy(shop, 5, '40000')
    buy(shop, 10, '45000', day='2026-09-02')
    sale = sell(shop, 8, '50000', day='2026-09-03')
    item = shop.sales.details(sale)[1][0]['id']
    first = shop.returns.post('2026-09-04', sale, [dict(sale_item_id=item, quantity=3)])
    second = shop.returns.post('2026-09-05', sale, [dict(sale_item_id=item, quantity=4)])
    assert shop.db.one('SELECT cogs_reversed FROM returns WHERE id=?', (first,))['cogs_reversed'] == money('120000')
    assert shop.db.one('SELECT cogs_reversed FROM returns WHERE id=?', (second,))['cogs_reversed'] == money('170000')
    assert [r['remaining_quantity'] for r in shop.stock.lots(shop.product)] == [5,9]
    assert shop.parties.balance(shop.customer) == money('50000')
    profit = shop.reports.period_profit('2026-09-01','2026-09-30')
    assert profit['net_sales'] == money('50000')
    assert profit['cogs'] == money('45000')
    assert profit['gross_profit'] == money('5000')


def test_return_refund_finance(shop):
    buy(shop)
    sale = sell(shop, paid='100000')
    item = shop.sales.details(sale)[1][0]['id']
    shop.returns.post('2026-09-03', sale, [dict(sale_item_id=item, quantity=1)], refund='50000', account_id=shop.cash)
    assert shop.parties.balance(shop.customer) == 0
    assert shop.money.accounts()[0]['balance'] == money('50000')
    assert shop.stock.totals()['quantity'] == 9


def test_return_repeated_quantities_rejected(shop):
    buy(shop)
    sale = sell(shop)
    item = shop.sales.details(sale)[1][0]['id']
    shop.returns.post('2026-09-03', sale, [dict(sale_item_id=item, quantity=1)])
    with pytest.raises(BusinessError):
        shop.returns.post('2026-09-04', sale, [dict(sale_item_id=item, quantity=2)])
    with pytest.raises(BusinessError):
        shop.returns.post('2026-09-04', sale, [dict(sale_item_id=item, quantity=1), dict(sale_item_id=item, quantity=1)])
    assert shop.stock.totals()['quantity'] == 9


def test_weighted_average_and_returns_separate(shop):
    buy(shop)
    sale = sell(shop,2,'50000')
    sell(shop,3,'55000')
    item = shop.sales.details(sale)[1][0]['id']
    shop.returns.post('2026-09-03',sale,[dict(sale_item_id=item,quantity=1)])
    r = shop.reports.product_sales('2026-09-01','2026-09-30')[0]
    assert r['average_rate'] == money('53000')
    assert r['net_quantity'] == 4
    assert r['net_sales'] == money('215000')


def test_transfer_expense_and_purchase_payment(shop):
    buy(shop, payments=[dict(account_id=shop.cash,amount='400000')])
    sell(shop, paid='100000')
    before = shop.reports.period_profit('2026-09-01','2026-09-30')
    shop.money.transfer('2026-09-03', shop.cash, shop.bank, '50000')
    assert shop.reports.period_profit('2026-09-01','2026-09-30') == before
    balances = {a['name']:a['balance'] for a in shop.money.accounts()}
    assert balances == {'Cash': money('350000')*-1, 'MJ Bank': money('50000')}
    shop.money.expense('2026-09-03','Rent','10000',shop.bank)
    after = shop.reports.period_profit('2026-09-01','2026-09-30')
    assert after['net_sales'] == before['net_sales']
    assert after['profit_after_expenses'] == before['gross_profit']-money('10000')


def test_multiline_sale_rollback_and_sequence(shop):
    buy(shop)
    other = shop.products.save(custom_name='Unstocked product')
    with pytest.raises(BusinessError):
        shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=2,selling_rate='50000'),dict(product_id=other,quantity=1,selling_rate='100')],customer_id=shop.customer)
    assert shop.db.one('SELECT COUNT(*) n FROM sales')['n'] == 0
    assert shop.db.one('SELECT COUNT(*) n FROM stock_allocations')['n'] == 0
    assert shop.stock.totals()['quantity'] == 10
    assert shop.db.setting('next_invoice') == '1'


def test_payment_failure_rolls_back_after_allocation(shop):
    buy(shop)
    with pytest.raises(BusinessError):
        shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='50000')], payments=[dict(account_id=999,amount='50000')])
    assert shop.stock.totals()['quantity'] == 10
    assert not shop.sales.list()


def test_multi_item_sale_and_return(shop):
    other=shop.products.save(custom_name='Used unlisted handset')
    shop.purchases.post('2026-09-01',[dict(product_id=shop.product,quantity=2,unit_price='100'),dict(product_id=other,quantity=2,unit_price='200')])
    sale=shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='150'),dict(product_id=other,quantity=1,selling_rate='250')],customer_id=shop.customer,payments=[dict(account_id=shop.cash,amount='100'),dict(account_id=shop.bank,amount='50')])
    assert shop.parties.balance(shop.customer)==money('250')
    items=shop.sales.details(sale)[1]
    ret=shop.returns.post('2026-09-03',sale,[dict(sale_item_id=i['id'],quantity=1) for i in items],refund='150',account_id=shop.cash)
    assert shop.stock.totals()['quantity']==4
    assert shop.parties.balance(shop.customer)==0
    shop.returns.void(ret,'Wrong return')
    assert shop.stock.totals()['quantity']==2
    assert shop.parties.balance(shop.customer)==money('250')


def test_void_policies(shop,owner_credentials):
    batch=buy(shop)
    sale=sell(shop,paid='100000')
    with pytest.raises(BusinessError):
        shop.purchases.void(batch,'Wrong batch',**owner_credentials)
    shop.sales.void(sale,'Wrong customer')
    assert shop.stock.totals()['quantity']==10
    assert shop.parties.balance(shop.customer)==0
    assert shop.money.accounts()[0]['balance']==0
    shop.purchases.void(batch,'Wrong batch',**owner_credentials)
    assert shop.stock.totals()['quantity']==0
    assert shop.reports.period_profit('2026-09-01','2026-09-30')['net_sales']==0


def test_return_blocks_sale_void_and_resale_blocks_return_void(shop):
    buy(shop)
    sale=sell(shop)
    item=shop.sales.details(sale)[1][0]['id']
    ret=shop.returns.post('2026-09-03',sale,[dict(sale_item_id=item,quantity=1)])
    with pytest.raises(BusinessError):
        shop.sales.void(sale,'Mistake')
    sell(shop,1,day='2026-09-04')
    with pytest.raises(BusinessError):
        shop.returns.void(ret,'Mistake')


def test_walk_in_and_anonymous_credit_rules(shop):
    buy(shop)
    with pytest.raises(BusinessError):
        shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='100')])
    sale=shop.sales.post('2026-09-02',[dict(product_id=shop.product,quantity=1,selling_rate='100')],payments=[dict(account_id=shop.cash,amount='100')])
    item=shop.sales.details(sale)[1][0]['id']
    with pytest.raises(BusinessError):
        shop.returns.post('2026-09-03',sale,[dict(sale_item_id=item,quantity=1)])
    shop.returns.post('2026-09-03',sale,[dict(sale_item_id=item,quantity=1)],refund='100',account_id=shop.cash)


def test_idempotency_and_conflicting_retry(shop):
    buy(shop)
    first=sell(shop,key='unique-1')
    assert sell(shop,key='unique-1')==first
    with pytest.raises(BusinessError):
        sell(shop,3,key='unique-1')
    assert shop.stock.totals()['quantity']==8


def test_openings_discounts_and_money_void(shop):
    shop.parties.adjustment(shop.customer,'2026-09-01','OPENING_BALANCE','70000','Excel cutover balance')
    pay=shop.money.collect(shop.customer,'2026-09-02',shop.cash,'20000')
    shop.parties.adjustment(shop.customer,'2026-09-03','DISCOUNT','5000','Agreed allowance')
    assert shop.parties.balance(shop.customer)==money('45000')
    shop.money.void('payment',pay,'Wrong collection')
    assert shop.parties.balance(shop.customer)==money('65000')
    assert shop.money.accounts()[0]['balance']==0
    assert shop.reports.period_profit('2026-09-01','2026-09-30')['profit_after_expenses']==-money('5000')


def test_backdated_stock_rejected(shop):
    buy(shop)
    sell(shop,day='2026-09-10')
    with pytest.raises(BusinessError):
        buy(shop,day='2026-09-05')
    with pytest.raises(BusinessError):
        sell(shop,day='2026-09-05')


def test_product_and_party_rename_preserve_snapshots(shop):
    buy(shop)
    sale=sell(shop)
    shop.products.save(product_id=shop.product,custom_name='Corrected new name')
    shop.parties.save('Corrected customer',party_id=shop.customer)
    h,items,_=shop.sales.details(sale)
    assert h['customer_snapshot']=='Dealer One'
    assert items[0]['product_description_snapshot']=='MI 11 Ultra 12/256 Shade'


@pytest.mark.parametrize('value',['-1','NaN','Infinity','1.234',0.1,True,'abc','1000000001'])
def test_bad_money(value):
    with pytest.raises(BusinessError):
        money(value)


@pytest.mark.parametrize('value',['0','-1','1.1',True,'1000001'])
def test_bad_quantity(value):
    with pytest.raises(BusinessError):
        quantity(value)


def test_exact_rounding_and_no_float_drift():
    assert money('0.10')+money('0.20')==money('0.30')
    assert price_line(dict(quantity=3,unit_price='0.005',exchange_rate='1',carry='0'),'CHINA_IMPORT')['line_total_cost']==3


def test_cash_summary_and_collection_only_day(shop):
    shop.money.collect(shop.customer,'2026-09-03',shop.cash,'100')
    rows=shop.reports.sales_summary('2026-09-01','2026-09-30')
    assert rows[0]['sales']==0 and rows[0]['collections']==money('100')
    cash=shop.reports.cash_summary('2026-09-04','2026-09-30')[0]
    assert cash['opening']==cash['closing']==money('100')
    assert cash['received']==0
def test_party_role_cannot_hide_customer_history(shop):
    shop.parties.adjustment(shop.customer,'2026-09-01','OPENING_BALANCE','70000','Cutover')
    with pytest.raises(BusinessError,match='Customer role'):
        shop.parties.save('Dealer One',party_id=shop.customer,is_customer=False,is_supplier=True)
    assert shop.reports.outstanding()[0]['balance']==money('70000')


def test_return_void_after_dependent_sale_correction(shop):
    buy(shop,2)
    original=sell(shop,2)
    item=shop.sales.details(original)[1][0]['id']
    ret=shop.returns.post('2026-09-03',original,[dict(sale_item_id=item,quantity=2)])
    later=sell(shop,1,day='2026-09-04')
    with pytest.raises(BusinessError,match='Stock has changed'):
        shop.returns.void(ret,'Wrong return')
    shop.sales.void(later,'Correct later sale first')
    shop.returns.void(ret,'Wrong return')
    assert shop.stock.totals()['quantity']==0
    assert shop.parties.balance(shop.customer)==money('100000')


def test_return_in_later_period_reverses_original_cost(shop):
    buy(shop,5,'40000')
    sale=sell(shop,2,'50000',day='2026-09-30')
    item=shop.sales.details(sale)[1][0]['id']
    shop.returns.post('2026-10-01',sale,[dict(sale_item_id=item,quantity=1)])
    september=shop.reports.period_profit('2026-09-01','2026-09-30')
    october=shop.reports.period_profit('2026-10-01','2026-10-31')
    assert september['gross_profit']==money('20000')
    assert october['net_sales']==-money('50000')
    assert october['cogs']==-money('40000')
    assert october['gross_profit']==-money('10000')
    report=shop.reports.product_sales('2026-10-01','2026-10-31')[0]
    assert report['average_rate'] is None
    assert report['net_quantity']==-1
