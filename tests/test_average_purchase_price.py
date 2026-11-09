"""Acquisition averages are an overview; original lots continue to cost sales."""
import pytest

from mobile_desk.values import money


def buy(shop, qty, unit_price, day='2026-10-01', **kwargs):
    return shop.purchases.post(day, [dict(product_id=shop.product,
        quantity=qty, unit_price=unit_price)], **kwargs)


def average(shop, product_id=None):
    product_id = shop.product if product_id is None else product_id
    return shop.products.purchase_averages([product_id])[product_id]


def test_unequal_batches_weight_pieces_instead_of_averaging_batch_prices(shop):
    buy(shop, 1, '12000')
    assert average(shop)['average_purchase_price'] == money('12000')
    buy(shop, 15, '25000', day='2026-10-02')
    assert average(shop) == dict(purchased_quantity=16,
        purchase_cost=money('387000'), average_purchase_price=money('24187.50'))
    assert shop.products.get(shop.product)['average_purchase_price'] == money('24187.50')
    assert shop.products.search('mi 11')[0]['average_purchase_price'] == money('24187.50')


def test_landed_average_includes_each_batches_carry_cost(shop):
    buy(shop, 2, '100', default_carry='10')
    buy(shop, 1, '200', day='2026-10-02', default_carry='30',
        carry_billed_to_supplier=True, supplier_id=shop.supplier)
    assert average(shop) == dict(purchased_quantity=3,
        purchase_cost=money('450'), average_purchase_price=money('150'))


def test_china_average_uses_saved_pkr_costs_and_each_historical_rate(shop):
    first = buy(shop, 3, '1000', purchase_type='CHINA_IMPORT', default_rate='40')
    second = buy(shop, 13, '700', day='2026-10-02',
        purchase_type='CHINA_IMPORT', default_rate='41')
    assert average(shop) == dict(purchased_quantity=16,
        purchase_cost=money('493100'), average_purchase_price=money('30818.75'))
    shop.money.add_rate('2026-10-03', '999')
    assert average(shop)['average_purchase_price'] == money('30818.75')
    assert shop.purchases.details(first)[1][0]['landed_unit_cost'] == money('40000')
    assert shop.purchases.details(second)[1][0]['landed_unit_cost'] == money('28700')


def test_purchase_average_does_not_reprice_fifo_or_change_with_customer_return(shop):
    buy(shop, 1, '100')
    buy(shop, 3, '200', day='2026-10-02')
    expected = dict(purchased_quantity=4, purchase_cost=money('700'),
        average_purchase_price=money('175'))
    sale = shop.sales.post('2026-10-03', [dict(product_id=shop.product,
        quantity=2, selling_rate='300')], customer_id=shop.customer)
    item = shop.sales.details(sale)[1][0]
    assert item['cogs'] == money('300')
    assert shop.stock.totals()['value'] == money('400')
    assert average(shop) == expected
    shop.returns.post('2026-10-04', sale, [dict(sale_item_id=item['id'], quantity=1)])
    assert shop.stock.totals()['value'] == money('500')
    assert average(shop) == expected


def test_sold_out_product_retains_purchase_average(shop):
    buy(shop, 1, '100')
    buy(shop, 3, '200', day='2026-10-02')
    shop.sales.post('2026-10-03', [dict(product_id=shop.product,
        quantity=4, selling_rate='300')], customer_id=shop.customer)
    assert shop.stock.totals() == dict(quantity=0, value=0)
    assert average(shop)['average_purchase_price'] == money('175')


def test_voided_purchase_excluded_and_opening_stock_included(shop):
    credentials = authorize_returns(shop)
    cancelled = buy(shop, 2, '100')
    buy(shop, 3, '200', day='2026-10-02', purchase_type='OPENING')
    shop.purchases.void(cancelled, 'Entered the cancelled batch by mistake', **credentials)
    assert average(shop) == dict(purchased_quantity=3,
        purchase_cost=money('600'), average_purchase_price=money('200'))
    assert len(shop.purchases.list()) == 2


def test_never_purchased_and_all_voided_have_no_average(shop):
    credentials = authorize_returns(shop)
    empty = dict(purchased_quantity=0, purchase_cost=0, average_purchase_price=None)
    assert average(shop) == empty
    batch = buy(shop, 1, '100')
    shop.purchases.void(batch, 'No purchase was completed', **credentials)
    assert average(shop) == empty


@pytest.mark.parametrize('first_qty,first_price,second_qty,second_price,expected', [
    (1, '0.01', 1, '0.02', 2),
    (2, '0.01', 1, '0.02', 1),
    (2, '0.02', 1, '0.01', 2),
])
def test_weighted_average_rounds_exact_paisa_half_up(shop, first_qty, first_price,
        second_qty, second_price, expected):
    buy(shop, first_qty, first_price)
    buy(shop, second_qty, second_price, day='2026-10-02')
    assert average(shop)['average_purchase_price'] == expected


def test_product_filter_keeps_products_and_missing_history_separate(shop):
    other = shop.products.save(custom_name='Huawei P30 Pro', aliases=['P thirty'], active=False)
    buy(shop, 2, '100')
    both = shop.products.purchase_averages()
    assert set(both) == {shop.product, other}
    assert both[other]['average_purchase_price'] is None
    assert shop.products.purchase_averages([]) == {}
    assert shop.products.purchase_averages([999999]) == {}
    assert shop.products.get(999999) is None
    filtered = shop.products.purchase_averages(x for x in [shop.product, shop.product])
    assert filtered == {shop.product: both[shop.product]}
    assert shop.products.search('P thirty', active_only=False)[0]['average_purchase_price'] is None


def authorize_returns(shop):
    credentials = dict(username='owner', password='Average cost owner 26!')
    shop.security.set_password(credentials['username'], credentials['password'], credentials['password'])
    return credentials


def return_lot(shop, batch, qty, day, credentials):
    lot = shop.purchases.details(batch)[1][0]['id']
    return shop.purchase_returns.post(batch, day,
        [dict(purchase_item_id=lot, quantity=qty)],
        reason='Shipment returned to the supplier', **credentials)


def test_partial_supplier_returns_remove_original_lot_cost_and_quantity(shop):
    credentials = authorize_returns(shop)
    cheap = buy(shop, 1, '12000', supplier_id=shop.supplier)
    dear = buy(shop, 15, '25000', day='2026-10-02', supplier_id=shop.supplier)
    return_lot(shop, dear, 3, '2026-10-03', credentials)
    assert average(shop) == dict(purchased_quantity=13,
        purchase_cost=money('312000'), average_purchase_price=money('24000'))
    return_lot(shop, cheap, 1, '2026-10-04', credentials)
    assert average(shop) == dict(purchased_quantity=12,
        purchase_cost=money('300000'), average_purchase_price=money('25000'))
    return_lot(shop, dear, 12, '2026-10-05', credentials)
    assert average(shop) == dict(purchased_quantity=0,
        purchase_cost=0, average_purchase_price=None)
    assert len(shop.purchases.list()) == 2
    assert len(shop.db.rows('SELECT * FROM purchase_return_items')) == 3


def test_in_transit_purchase_and_partial_cancellation_use_acquired_quantities(shop):
    credentials = authorize_returns(shop)
    transit = buy(shop, 5, '100', supplier_id=shop.supplier, received=False)
    buy(shop, 5, '300', day='2026-10-02', supplier_id=shop.supplier)
    assert shop.stock.totals()['quantity'] == 5
    assert average(shop) == dict(purchased_quantity=10,
        purchase_cost=money('2000'), average_purchase_price=money('200'))
    return_lot(shop, transit, 2, '2026-10-03', credentials)
    assert shop.stock.totals()['quantity'] == 5
    assert average(shop) == dict(purchased_quantity=8,
        purchase_cost=money('1800'), average_purchase_price=money('225'))
    shop.purchases.receive(transit, '2026-10-04')
    assert shop.stock.totals()['quantity'] == 8
    assert average(shop)['average_purchase_price'] == money('225')
