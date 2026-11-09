"""Repeatable synthetic-volume benchmark, isolated from all shop data."""
from pathlib import Path
import json
import sys
from time import perf_counter
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mobile_desk.context import Context


with TemporaryDirectory(prefix='mobile-desk-benchmark-') as temp:
    ctx=Context(Path(temp),install_catalogue=False)
    customer=ctx.parties.save('Synthetic benchmark customer')
    stamp='2026-01-01T00:00:00.000000+00:00'
    with ctx.db.connect(write=True) as c:
        for product in range(1,5001):
            name=f'Synthetic phone {product:05d}'
            c.execute('INSERT INTO products(id,custom_name,normalized_search_name,created_at,updated_at) VALUES(?,?,?,?,?)',(product,name,name.lower(),stamp,stamp))
            batch=c.execute("INSERT INTO purchase_batches(reference,transaction_date,purchase_type,supplier_snapshot,currency,total,notes,created_at) VALUES(?,'2019-01-01','OPENING','','PKR',800000,'Synthetic volume fixture',?)",(f'BENCH-{product}',stamp)).lastrowid
            lot=c.execute("INSERT INTO purchase_items(purchase_batch_id,product_id,quantity,original_currency,pkr_unit_purchase_cost,additional_cost_per_unit,landed_unit_cost,line_total_cost,product_description_snapshot,created_at) VALUES(?,?,20,'PKR',40000,0,40000,800000,?,?)",(batch,product,name,stamp)).lastrowid
            c.execute("INSERT INTO stock_movements(purchase_item_id,transaction_date,quantity,kind,reference_id,created_at) VALUES(?,'2019-01-01',20,'PURCHASE',?,?)",(lot,batch,stamp))
            for year in range(2021,2026):
                date=f'{year}-09-01'
                sale=c.execute('INSERT INTO sales(invoice_number,transaction_date,customer_id,customer_snapshot,subtotal,total,notes,created_at) VALUES(?,?,?, ?,60000,60000,?,?)',(f'B-{product}-{year}',date,customer,'Synthetic benchmark customer','Synthetic volume fixture',stamp)).lastrowid
                item=c.execute('INSERT INTO sale_items(sale_id,product_id,quantity,selling_rate,line_total,cogs,gross_profit,product_description_snapshot) VALUES(?,?,1,60000,60000,40000,20000,?)',(sale,product,name)).lastrowid
                c.execute('INSERT INTO stock_allocations(sale_item_id,purchase_item_id,quantity,unit_cost) VALUES(?,?,1,40000)',(item,lot))
                c.execute("INSERT INTO stock_movements(purchase_item_id,transaction_date,quantity,kind,reference_id,created_at) VALUES(?,?,-1,'SALE',?,?)",(lot,date,item,stamp))
    functions={
        'sales_page_100':lambda:ctx.sales.list(limit=100),
        'stock_page_100':lambda:ctx.stock.current(limit=100),
        'dashboard':lambda:ctx.reports.dashboard('2025-09-30'),
        'five_year_product_report':lambda:ctx.reports.product_sales('2021-01-01','2025-12-31'),
        'customer_statement_25000_rows':lambda:ctx.parties.statement(customer),
    }
    results={}
    for name,fn in functions.items():
        start=perf_counter()
        value=fn()
        results[name]=dict(milliseconds=round((perf_counter()-start)*1000,2),rows=len(value))
    assert ctx.stock.totals()['quantity']==75000
    assert ctx.parties.balance(customer)==1500000000
    report=dict(products=5000,invoices=25000,purchase_lots=5000,stock_movements=30000,financial_integrity='passed',queries=results)
    target=Path(__file__).resolve().parents[1]/'docs/qa/business-performance.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
