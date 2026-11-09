import pytest
from mobile_desk.values import BusinessError,money


def test_duplicate_contact_names_are_blocked_across_roles_and_inactive_accounts(shop):
    identity=shop.parties.save('Karachi Supply',is_customer=False,is_supplier=True,active=False)
    before=shop.db.one('SELECT COUNT(*) n FROM parties')['n']
    for name in (' KARACHI   supply ','Karachi-Supply','karachi supply'):
        with pytest.raises(BusinessError,match='already exists'):
            shop.parties.save(name)
    assert shop.db.one('SELECT COUNT(*) n FROM parties')['n']==before
    assert shop.db.one('SELECT active FROM parties WHERE id=?',(identity,))['active']==0


def test_edit_contact_roles_and_rename_collision(shop):
    shop.parties.save('Supplier One',party_id=shop.supplier,is_customer=True,is_supplier=True)
    assert shop.db.one('SELECT is_customer FROM parties WHERE id=?',(shop.supplier,))['is_customer']==1
    with pytest.raises(BusinessError,match='already exists'):
        shop.parties.save('supplier one',party_id=shop.customer)
    assert shop.db.one('SELECT name FROM parties WHERE id=?',(shop.customer,))['name']=='Dealer One'


def test_legacy_duplicate_accounts_keep_their_identity_and_history(shop):
    with shop.db.connect(write=True) as c:
        duplicate=c.execute("INSERT INTO parties(name,normalized_name,is_customer,is_supplier,phone,address,notes,active,created_at) SELECT name,normalized_name,is_customer,is_supplier,'0300-2222222',address,notes,active,created_at FROM parties WHERE id=?",(shop.supplier,)).lastrowid
    shop.parties.adjustment(shop.supplier,'2026-10-01','OPENING_BALANCE','10000','First account',role='SUPPLIER')
    shop.parties.adjustment(duplicate,'2026-10-01','OPENING_BALANCE','50000','Second account',role='SUPPLIER')
    shop.parties.save('Supplier One',party_id=duplicate,is_customer=False,is_supplier=True,phone='0300-3333333')
    rows=shop.parties.search('supplier one',role='is_supplier')
    assert len(rows)==2 and all(row['name_count']==2 for row in rows)
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('10000')
    assert shop.parties.balance(duplicate,role='SUPPLIER')==money('50000')
    with pytest.raises(BusinessError,match='already exists'):
        shop.parties.save('Supplier One',is_customer=False,is_supplier=True)


def test_repeat_purchases_share_one_supplier_and_later_payment_creates_no_invoice(shop):
    for price in ('10000','50000'):
        shop.purchases.post('2026-10-01',[dict(product_id=shop.product,quantity=1,unit_price=price)],supplier_id=shop.supplier)
    purchases=shop.purchases.list()
    assert len(purchases)==2
    assert len({row['reference'] for row in purchases})==2
    assert {row['supplier_id'] for row in purchases}=={shop.supplier}
    assert len(shop.parties.search(role='is_supplier'))==1
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('60000')
    shop.money.pay_supplier(shop.supplier,'2026-10-02',shop.cash,'20000')
    assert shop.parties.balance(shop.supplier,role='SUPPLIER')==money('40000')
    assert shop.parties.balance(shop.supplier)==0
    assert len(shop.purchases.list())==2 and not shop.sales.list()
