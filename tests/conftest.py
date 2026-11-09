from pathlib import Path
import pytest
from mobile_desk.context import Context


@pytest.fixture
def shop(tmp_path):
    context = Context(tmp_path, install_catalogue=False)
    context.product = context.products.save(custom_name='MI 11 Ultra 12/256 Shade')
    context.customer = context.parties.save('Dealer One')
    context.supplier = context.parties.save('Supplier One', is_customer=False, is_supplier=True)
    context.cash = context.money.accounts()[0]['id']
    context.bank = context.money.account('MJ Bank')
    return context


@pytest.fixture
def owner_credentials(shop):
    credentials=dict(username='test-owner',password='Test owner password 26!')
    shop.security.set_password(credentials['username'],credentials['password'],credentials['password'])
    return credentials
