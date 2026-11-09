import json
import pytest
from mobile_desk.values import BusinessError,money


def test_purchase_list_shows_saved_phone_names_without_rounding_or_stack_duplicates(shop):
    other=shop.products.save(custom_name='Huawei P30 Pro')
    batch=shop.purchases.post('2026-10-01',[
        dict(product_id=shop.product,quantity=6,unit_price='1000',carry='1'),
        dict(product_id=shop.product,quantity=3,unit_price='950',carry='2'),
        dict(product_id=other,quantity=2,unit_price='500',carry='1')],
        purchase_type='CHINA_IMPORT',default_rate='40',carry_currency='CNY',carry_basis='STACK_TOTAL',supplier_id=shop.supplier)
    assert len(shop.purchases.details(batch)[1])>3
    row=shop.purchases.list()[0]
    assert row['product_names']=='MI 11 Ultra 12/256 Shade; Huawei P30 Pro'
    shop.products.save(product_id=other,custom_name='Renamed product')
    assert shop.purchases.list(query='Huawei P30')[0]['product_names']==row['product_names']
    assert len(shop.purchases.list(query='Huawei P30',limit=1))==1


def test_purchase_product_column_retains_filters_and_one_row_per_purchase(shop):
    other=shop.products.save(custom_name='Samsung Galaxy A55')
    for name,product,kind in [('FIRST',shop.product,'LOCAL'),('SECOND',other,'CHINA_IMPORT')]:
        shop.purchases.post('2026-10-01',[dict(product_id=product,quantity=1,unit_price='100')],supplier_id=shop.supplier,reference=name,purchase_type=kind,default_rate='40')
    rows=shop.purchases.list()
    assert len(rows)==2
    assert shop.purchases.list(kind='CHINA_IMPORT')[0]['product_names']=='Samsung Galaxy A55'
    assert shop.purchases.list(supplier_id=shop.supplier,limit=1,offset=1)[0]['reference']=='FIRST'


def test_return_and_cancellation_need_no_reason_but_still_require_owner(shop,owner_credentials):
    for received in (True,False):
        batch=shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=2,unit_price='100')],supplier_id=shop.supplier,received=received)
        lot=shop.purchases.details(batch)[1][0]
        lines=[dict(purchase_item_id=lot['id'],quantity=2)]
        with pytest.raises(BusinessError,match='Incorrect owner'):
            shop.purchase_returns.post(batch,'2026-10-02',lines)
        returned=shop.purchase_returns.post(batch,'2026-10-02',lines,**owner_credentials)
        record=shop.purchase_returns.details(returned)['header']
        assert record['reason']==('Stock returned to supplier' if received else 'Shipment cancelled')
        audit=shop.db.one("SELECT reason FROM audit_log WHERE entity='purchase_return' AND entity_id=?",(str(returned),))
        evidence=json.loads(audit['reason'])
        assert evidence['reason']==record['reason'] and evidence['owner_username']=='test-owner'
    assert shop.stock.totals()['quantity']==0


def test_reason_free_corrections_keep_action_details_and_dependencies(shop,owner_credentials):
    purchase=shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=2,unit_price='100')],supplier_id=shop.supplier)
    sale=shop.sales.post('2026-10-02',[dict(product_id=shop.product,quantity=1,selling_rate='150')],customer_id=shop.customer)
    with pytest.raises(BusinessError,match='dependent sale'):
        shop.purchases.void(purchase,**owner_credentials)
    shop.sales.void(sale)
    assert shop.sales.details(sale)[0]['void_reason']=='Sale entry undone'
    entry=shop.corrections.latest()
    shop.corrections.undo_latest(entry['audit_id'],**owner_credentials)
    assert shop.purchases.details(purchase)[0]['void_reason']=='Purchase entry undone'
    assert shop.stock.totals()['quantity']==0
    identity=shop.money.expense('2026-10-03','Transport','20',shop.cash)
    shop.money.void('expense',identity)
    assert shop.db.one('SELECT void_reason FROM expenses WHERE id=?',(identity,))['void_reason']=='Expense entry undone'


def test_adjustment_auto_description_does_not_change_balances(shop):
    identity=shop.parties.adjustment(shop.customer,'2026-10-01','OPENING_BALANCE','100')
    assert shop.parties.balance(shop.customer)==money('100')
    assert shop.db.one('SELECT reason FROM party_adjustments WHERE id=?',(identity,))['reason']=='Opening balance entered'
    payment=shop.money.collect(shop.customer,'2026-10-02',shop.cash,'40')
    shop.money.void('payment',payment)
    assert shop.parties.balance(shop.customer)==money('100')
