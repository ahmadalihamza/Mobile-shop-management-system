"""Verify the training examples in a temporary shop; never populate client/practice records."""
import json
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mobile_desk.context import Context
from mobile_desk.values import BusinessError,amount_text,money
from mobile_desk.catalogue import models_checksum

DAY='2026-10-01'
OPENING='2026-09-30'
ROOT=Path(__file__).resolve().parents[1]


def verify():
    with TemporaryDirectory(prefix='mobile-desk-training-check-') as temporary:
        ctx=Context(Path(temporary)/'shop')
        username,password='practice-verifier',secrets.token_urlsafe(24)
        ctx.security.set_password(username,password,password)
        credentials=dict(username=username,password=password)
        ctx.money.save_settings(shop_name='Mobile Desk PRACTICE',invoice_prefix='PR-',setup_complete='1')
        cash=ctx.money.accounts()[0]['id']
        bank=ctx.money.account('Practice Bank')
        clean=ctx.backups.create(Path(temporary)/'01-CleanSetup')
        ctx.money.account('Cash','CASH','500000',OPENING,account_id=cash)
        ctx.money.account('Practice Bank','BANK','300000',OPENING,account_id=bank)
        samsung=ctx.products.save(custom_name='Samsung Galaxy A55 8/256 Navy',brand='Samsung',model='Galaxy A55',ram='8',storage='256',color='Navy',aliases=['a55navy'])
        xiaomi=ctx.products.save(custom_name='Xiaomi Redmi Note 14 8/256 Black',aliases=['note14black'])
        used=ctx.products.save(custom_name='Practice Used Phone 6/128',aliases=['used128'])
        ali=ctx.parties.save('Ali Dealer')
        karachi=ctx.parties.save('Karachi Supply',is_customer=False,is_supplier=True)
        china=ctx.parties.save('China Supply',is_customer=False,is_supplier=True)
        ctx.parties.adjustment(ali,OPENING,'OPENING_BALANCE','20000','Agreed previous customer debt')
        ctx.parties.adjustment(karachi,OPENING,'OPENING_BALANCE','10000','Agreed previous supplier debt',role='SUPPLIER')
        ctx.money.add_rate(DAY,'40','Practice rate, not a live exchange quote')
        records=[]
        def checkpoint(name,quantity,value,cash_balance,bank_balance,ali_balance,karachi_balance,china_balance):
            expected=dict(stock_pieces=quantity,stock_value=money(value),cash=money(cash_balance),bank=money(bank_balance),ali=money(ali_balance),karachi=money(karachi_balance),china=money(china_balance))
            actual=dict(stock_pieces=ctx.stock.totals()['quantity'],stock_value=ctx.stock.totals()['value'],cash=next(a['balance'] for a in ctx.money.accounts() if a['id']==cash),bank=next(a['balance'] for a in ctx.money.accounts() if a['id']==bank),ali=ctx.parties.balance(ali),karachi=ctx.parties.balance(karachi,role='SUPPLIER'),china=ctx.parties.balance(china,role='SUPPLIER'))
            assert actual==expected,(name,expected,actual)
            records.append(dict(stage=name,**{k:(v if k=='stock_pieces' else amount_text(v)) for k,v in actual.items()}))
        ctx.purchases.post(DAY,[dict(product_id=samsung,quantity=2,unit_price='40000'),dict(product_id=used,quantity=1,unit_price='15000')],purchase_type='OPENING',reference='OPEN-TRAIN-1')
        checkpoint('Opening state',3,'95000','500000','300000','20000','10000','0')
        openings=ctx.backups.create(Path(temporary)/'02-Openings')
        ctx.purchases.post(DAY,[dict(product_id=samsung,quantity=3,unit_price='42000',carry='1000')],supplier_id=karachi,reference='LOCAL-TRAIN-1',carry_billed_to_supplier=True,payments=[dict(account_id=bank,amount='79000')])
        checkpoint('Local purchase',6,'224000','500000','221000','20000','60000','0')
        china_batch=ctx.purchases.post(DAY,[dict(product_id=xiaomi,quantity=4,unit_price='1000',carry='2000')],purchase_type='CHINA_IMPORT',default_rate='40',supplier_id=china,reference='CHINA-TRAIN-1',payments=[dict(account_id=bank,amount='100000')],carry_payment='3000',carry_account_id=cash)
        checkpoint('China purchase',10,'392000','497000','121000','20000','60000','60000')
        first=ctx.sales.post(DAY,[dict(product_id=samsung,quantity=1,selling_rate='50000')],payments=[dict(account_id=cash,amount='50000')])
        checkpoint('Sale 1, cash walk-in',9,'352000','547000','121000','20000','60000','60000')
        second=ctx.sales.post(DAY,[dict(product_id=samsung,quantity=2,selling_rate='52000'),dict(product_id=xiaomi,quantity=1,selling_rate='50000')],customer_id=ali,payments=[dict(account_id=cash,amount='40000'),dict(account_id=bank,amount='60000')])
        checkpoint('Sale 2, multi-product split partial',6,'227000','587000','181000','74000','60000','60000')
        third=ctx.sales.post(DAY,[dict(product_id=used,quantity=1,selling_rate='20000')],customer_id=ali)
        fourth=ctx.sales.post(DAY,[dict(product_id=xiaomi,quantity=1,selling_rate='51000')],payments=[dict(account_id=bank,amount='51000')])
        checkpoint('Sales 3 and 4, credit and bank walk-in',4,'170000','587000','232000','94000','60000','60000')
        ctx.money.collect(ali,DAY,bank,'60000',reference='ALI-COLLECT-1')
        docs=ctx.parties.documents(ali)
        assert [(d['reference'],d['outstanding']) for d in docs]==[('ADJ-1',0),('PR-000002',money('14000')),('PR-000003',money('20000'))],docs
        ctx.money.pay_supplier(karachi,DAY,cash,'60000',reference='KARACHI-PAY-1')
        ctx.money.pay_supplier(china,DAY,bank,'30000',reference='CHINA-PAY-1')
        checkpoint('Later customer and supplier payments',4,'170000','527000','262000','34000','0','30000')
        returned=next(i for i in ctx.sales.details(second)[1] if i['product_id']==xiaomi)
        ctx.returns.post(DAY,second,[dict(sale_item_id=returned['id'],quantity=1)],refund='20000',account_id=cash,notes='Practice customer return, saleable phone')
        checkpoint('Customer return and partial refund',5,'212000','507000','262000','4000','0','30000')
        ctx.money.pay_carry(china_batch,DAY,cash,'5000','Remaining practice transport cost')
        ctx.money.expense(DAY,'Practice shop rent','10000',cash,'Rent')
        ctx.money.expense(DAY,'Practice delivery expense','2000',cash,'Delivery')
        ctx.money.transfer(DAY,cash,bank,'50000','CASH-TO-BANK-1')
        ctx.parties.adjustment(ali,DAY,'DISCOUNT','4000','Agreed customer settlement discount')
        checkpoint('Completed trading day',5,'212000','440000','312000','0','0','30000')
        profit=ctx.reports.period_profit(DAY,DAY)
        expected_profit=dict(sales_before_returns='275000',returns='50000',net_sales='225000',cogs='180000',gross_profit='45000',recorded_expenses='12000',discounts='4000',profit_after_expenses='29000')
        assert all(profit[k]==money(v) for k,v in expected_profit.items()),profit
        summary=ctx.reports.sales_summary(DAY,DAY)[0]
        assert summary['quantity']==6 and summary['receipts']==money('201000') and summary['collections']==money('60000') and summary['credit_sales']==money('74000')
        assert [h['invoice_number'] for h in [ctx.sales.details(i)[0] for i in (first,second,third,fourth)]]==['PR-000001','PR-000002','PR-000003','PR-000004']
        product_profit=ctx.reports.product_sales(DAY,DAY)
        assert {r['product_id']:r['gross_profit'] for r in product_profit}=={samsung:money('31000'),xiaomi:money('9000'),used:money('5000')}
        cash_summary=ctx.reports.cash_summary(DAY,DAY)
        assert [(r['opening'],r['received'],r['paid_out'],r['closing']) for r in cash_summary]==[
            tuple(map(money,('500000','90000','150000','440000'))),tuple(map(money,('300000','221000','209000','312000')))]
        completed=ctx.backups.create(Path(temporary)/'03-CompletedDay')
        def restore():
            nonlocal ctx
            ctx.backups.restore(completed,**credentials)
            ctx=Context(ctx.root)
        # Isolated optional exercises, each restored to the completed-day checkpoint.
        ctx.money.collect(ali,DAY,bank,'10000')
        assert ctx.parties.balance(ali)==-money('10000')
        entry=ctx.corrections.latest();ctx.corrections.undo_latest(entry['audit_id'],'Practice advance undone')
        assert ctx.parties.balance(ali)==0
        ctx.money.pay_supplier(china,DAY,bank,'40000')
        assert ctx.parties.balance(china,role='SUPPLIER')==-money('10000')
        entry=ctx.corrections.latest();ctx.corrections.undo_latest(entry['audit_id'],'Practice supplier advance undone')
        assert ctx.parties.balance(china,role='SUPPLIER')==money('30000')
        both=ctx.parties.save('Bilal Trade',is_customer=True,is_supplier=True)
        ctx.parties.adjustment(both,OPENING,'OPENING_BALANCE','5000','Practice customer opening')
        ctx.parties.adjustment(both,OPENING,'OPENING_BALANCE','7000','Practice supplier opening',role='SUPPLIER')
        ctx.money.collect(both,DAY,cash,'2000');ctx.money.pay_supplier(both,DAY,bank,'3000')
        assert ctx.parties.balance(both)==money('3000') and ctx.parties.balance(both,role='SUPPLIER')==money('4000')
        restore()
        ctx.parties.adjustment(ali,DAY,'MANUAL_DEBIT','2000','Practice correction only')
        ctx.parties.adjustment(ali,DAY,'MANUAL_CREDIT','500','Practice correction only')
        ctx.parties.adjustment(ali,DAY,'DISCOUNT','500','Practice discount')
        assert ctx.parties.balance(ali)==money('1000') and ctx.reports.period_profit(DAY,DAY)['profit_after_expenses']==money('28500')
        ctx.parties.adjustment(china,DAY,'MANUAL_DEBIT','1000','Practice supplier correction',role='SUPPLIER')
        ctx.parties.adjustment(china,DAY,'MANUAL_CREDIT','1000','Practice supplier correction',role='SUPPLIER')
        assert ctx.parties.balance(china,role='SUPPLIER')==money('30000')
        restore()
        ctx.money.add_rate(DAY,'41','Second practice rate')
        batch=ctx.purchases.post(DAY,[dict(product_id=xiaomi,quantity=1,unit_price='1000',exchange_rate='41')],purchase_type='CHINA_IMPORT',default_rate='41',supplier_id=china,reference='FX-TRAIN-2')
        assert ctx.purchases.details(china_batch)[1][0]['landed_unit_cost']==money('42000')
        assert ctx.purchases.details(batch)[1][0]['landed_unit_cost']==money('41000')
        restore()
        override=ctx.purchases.post(DAY,[dict(product_id=xiaomi,quantity=1,unit_price='1000',exchange_rate='41.5',carry='1000')],purchase_type='CHINA_IMPORT',default_rate='41',supplier_id=china,reference='FX-OVERRIDE-1')
        assert ctx.purchases.details(override)[1][0]['landed_unit_cost']==money('42500')
        assert ctx.parties.balance(china,role='SUPPLIER')==money('71500')
        restore()
        used_item=ctx.sales.details(third)[1][0]
        ctx.returns.post(DAY,third,[dict(sale_item_id=used_item['id'],quantity=1)],refund='0')
        assert ctx.stock.totals()==dict(quantity=6,value=money('227000')) and ctx.parties.balance(ali)==-money('20000')
        assert ctx.reports.period_profit(DAY,DAY)['profit_after_expenses']==money('24000')
        restore()
        walkin_item=ctx.sales.details(first)[1][0]
        ctx.returns.post(DAY,first,[dict(sale_item_id=walkin_item['id'],quantity=1)],refund='50000',account_id=cash)
        assert ctx.stock.totals()['quantity']==6 and ctx.money.accounts()[0]['balance']==money('390000')
        restore()
        paid_purchase=ctx.purchases.post(DAY,[dict(product_id=used,quantity=1,unit_price='18000')],reference='UNDO-LOCAL-1',payments=[dict(account_id=cash,amount='18000')])
        paid_sale=ctx.sales.post(DAY,[dict(product_id=used,quantity=1,selling_rate='22000')],payments=[dict(account_id=cash,amount='22000')])
        try:ctx.purchases.void(paid_purchase,'Try unsafe undo',**credentials)
        except BusinessError:pass
        else:raise AssertionError('Paid purchase dependency was not protected')
        ctx.sales.void(paid_sale,'Correct dependent sale first');ctx.purchases.void(paid_purchase,'Correct purchase',**credentials)
        assert ctx.stock.totals()==dict(quantity=5,value=money('212000')) and ctx.money.accounts()[0]['balance']==money('440000')
        restore()
        for operation in (
            lambda:ctx.sales.post(DAY,[dict(product_id=samsung,quantity=99,selling_rate='50000')],payments=[dict(account_id=cash,amount='4950000')]),
            lambda:ctx.sales.post(DAY,[dict(product_id=samsung,quantity=1,selling_rate='50000')]),
            lambda:ctx.sales.post(DAY,[dict(product_id=samsung,quantity=1,selling_rate='50000')],payments=[dict(account_id=cash,amount='60000')]),
            lambda:ctx.money.transfer(DAY,cash,cash,'1000'),
        ):
            try:operation()
            except BusinessError:pass
            else:raise AssertionError('Expected validation did not block an invalid exercise')
        ctx.money.expense(DAY,'Mistaken learning expense','1000',cash)
        entry=ctx.corrections.latest();ctx.corrections.undo_latest(entry['audit_id'],'Wrong example expense')
        assert ctx.money.accounts()[0]['balance']==money('440000')
        try:ctx.purchases.void(ctx.purchases.list(query='LOCAL-TRAIN-1')[0]['id'],'Unsafe older purchase reversal',**credentials)
        except BusinessError:pass
        else:raise AssertionError('Used purchase incorrectly reversed')
        sample=json.loads((ROOT/'practice/Sample-Catalogue-Update.json').read_text(encoding='utf-8'))
        assert sample['sha256']==models_checksum(sample['models'])
        before=ctx.stock.totals();ctx.catalogue.import_package(sample)
        assert ctx.catalogue.search('learningphone') and ctx.stock.totals()==before
        restore()
        count=ctx.catalogue.info()['count']
        safety=ctx.reset.reset(username,password,'RESET')
        assert not ctx.products.search() and ctx.stock.totals()['quantity']==0 and all(a['balance']==0 for a in ctx.money.accounts())
        assert ctx.catalogue.info()['count']==count and ctx.security.configured
        ctx.backups.restore(safety,**credentials);ctx=Context(ctx.root)
        checkpoint('Recovered after reset',5,'212000','440000','312000','0','0','30000')
        ctx.backups.restore(openings,**credentials);ctx=Context(ctx.root)
        checkpoint('Restarted from opening backup',3,'95000','500000','300000','20000','10000','0')
        ctx.backups.restore(clean,**credentials);ctx=Context(ctx.root)
        assert not ctx.products.search() and all(a['balance']==0 for a in ctx.money.accounts())
        return dict(status='passed',records_created_only_in_temporary_directory=True,practice_shop_not_populated=True,day=DAY,opening_date=OPENING,checkpoints=records,profit={k:amount_text(profit[k]) for k in expected_profit},product_profit=[dict(product=r['custom_name'],sold=r['quantity'],returned=r['returned_quantity'],gross_profit=amount_text(r['gross_profit'])) for r in product_profit],cash_bank_summary=[dict(account=r['name'],**{k:amount_text(r[k]) for k in ('opening','received','paid_out','closing')}) for r in cash_summary],daily_sales={k:summary[k] if k in ('quantity','invoices') else amount_text(summary[k]) for k in ('quantity','invoices','sales','receipts','credit_sales','collections','returns','net_sales')},additional_exercises=['customer advance','supplier advance','dual-role independent balances','manual adjustments and discounts','FX snapshot protection','per-line FX override','named customer return with no refund','walk-in full refund','fully paid local purchase without supplier','invalid stock/credit/overpayment/transfer blocked','expense undo','used purchase undo blocked','catalogue update independent of stock','full reset and recovery','opening/clean backup restart'])


if __name__=='__main__':
    result=verify()
    (ROOT/'docs/qa/practice-walkthrough-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
