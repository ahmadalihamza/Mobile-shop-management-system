"""Windows application entry point, with isolated diagnostic launch support."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
from PySide6.QtCore import QLockFile,QTimer
from PySide6.QtWidgets import QApplication,QMessageBox
from mobile_desk.context import Context
from mobile_desk.paths import data_root,resource_path
from mobile_desk.ui.common import STYLE
from mobile_desk.ui.main_window import MainWindow
from mobile_desk.values import today


def seed_demo(ctx):
    if ctx.products.search(limit=1):
        return
    ctx.money.save_settings(shop_name='Mobile Desk — Practice Shop',setup_complete='1')
    customer=ctx.parties.save('Sample Dealer')
    supplier=ctx.parties.save('Sample Supplier',is_customer=False,is_supplier=True)
    bank=ctx.money.account('MJ Bank')
    cash=ctx.money.accounts()[0]['id']
    products=[ctx.products.save(custom_name=name) for name in ('MI 11 Ultra 12/256 Shade','Samsung Galaxy A55 8/256 Navy','Nothing Phone (2) 12/256')]
    day=today()
    ctx.purchases.post(day,[dict(product_id=products[0],quantity=20,unit_price='1000',carry='4000'),dict(product_id=products[1],quantity=10,unit_price='1300',carry='4000')],purchase_type='CHINA_IMPORT',default_rate='40.3',supplier_id=supplier,reference='PRACTICE-CHINA-1')
    ctx.purchases.post(day,[dict(product_id=products[2],quantity=8,unit_price='55000')],supplier_id=supplier)
    ctx.sales.post(day,[dict(product_id=products[0],quantity=3,selling_rate='62000'),dict(product_id=products[1],quantity=2,selling_rate='75000')],customer_id=customer,payments=[dict(account_id=cash,amount='100000'),dict(account_id=bank,amount='50000')])
    ctx.money.collect(customer,day,bank,'25000')
    ctx.money.expense(day,'Sample delivery expense','1500',cash,'Delivery')


def smoke_capture(window,output):
    from mobile_desk.ui.transactions import TransactionDialog,ReturnDialog
    from mobile_desk.ui.products import ProductDialog
    from mobile_desk.ui.people_money import PaymentDialog,PartyChooser,AdjustmentDialog
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance()
    results=[]
    try:
        window.resize(1366,768)
        for i,title in enumerate(('dashboard','sales','purchases','stock','suppliers','customers','money','reports','settings')):
            window.navigate(i)
            app.processEvents()
            window.grab().save(str(output/(title+'.png')))
            results.append(title)
        products=window.ctx.products.search(limit=1)
        product=products[0] if products else None
        dialogs=[('new_sale',TransactionDialog(window,window.ctx)),('new_purchase_local',TransactionDialog(window,window.ctx,True)),('new_purchase_china',TransactionDialog(window,window.ctx,True)),('new_product',ProductDialog(window,window.ctx)),('receive_payment',PaymentDialog(window,window.ctx)),('pay_supplier',PaymentDialog(window,window.ctx,supplier=True))]
        for name,dialog in dialogs:
            if isinstance(dialog,TransactionDialog) and product:
                if name=='new_purchase_china':
                    dialog.type.setCurrentIndex(1)
                    dialog.extra_costs.setChecked(True)
                    dialog.carry.setText('4000')
                dialog.add_product(product)
                dialog.entries[0]['price'].setText('1000' if dialog.purchase else '62000')
                dialog.entries[0]['qty'].setValue(3)
                if not dialog.purchase:
                    dialog.pay_full()
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(output/(name+'.png')))
            results.append(name)
            dialog.close()
        chooser=PartyChooser(window,window.ctx,supplier=True,allow_new=True)
        chooser.show()
        app.processEvents()
        chooser.grab().save(str(output/'choose_existing_supplier.png'))
        results.append('choose_existing_supplier')
        chooser.tabs.setCurrentIndex(1)
        chooser.new_fields.name.setText('New supplier example')
        chooser.new_fields.phone.setText('0300-1234567')
        app.processEvents()
        chooser.grab().save(str(output/'add_new_supplier.png'))
        results.append('add_new_supplier')
        chooser.close()
        payment_chooser=PartyChooser(window,window.ctx,supplier=True)
        payment_chooser.show()
        app.processEvents()
        payment_chooser.grab().save(str(output/'supplier_payment_list.png'))
        results.append('supplier_payment_list')
        payment_chooser.close()
        customers=window.ctx.parties.search(role='is_customer',active_only=True,limit=1)
        if customers:
            adjustment=AdjustmentDialog(window,window.ctx,customers[0]['id'])
            adjustment.amount.setText('10000')
            adjustment.show()
            app.processEvents()
            adjustment.grab().save(str(output/'reason_free_balance_adjustment.png'))
            results.append('reason_free_balance_adjustment')
            adjustment.close()
        purchases=window.ctx.purchases.list(limit=1)
        if purchases:
            purchase_undo=window.purchase_undo_dialog(purchases[0])
            purchase_undo.show()
            app.processEvents()
            purchase_undo.grab().save(str(output/'reason_free_purchase_undo.png'))
            results.append('reason_free_purchase_undo')
            purchase_undo.close()
        from PySide6.QtWidgets import QDialog,QVBoxLayout
        cat=QDialog(window)
        cat.resize(1100,720)
        cat_layout=QVBoxLayout(cat)
        cat_layout.addWidget(window.catalogue_page())
        cat.show()
        app.processEvents()
        cat.grab().save(str(output/'mobile_catalogue.png'))
        results.append('mobile_catalogue')
        cat.close()
        from mobile_desk.diagnostics import release_flow
        from datetime import datetime
        flow=release_flow(window.ctx.root/('release-flow-'+datetime.now().strftime('%Y%m%d%H%M%S%f')),output)
        results.append('return_sale')
        results.extend(('owner_password','undo_last_entry','reset_all_data','owner_restore'))
        from mobile_desk.import_diagnostics import import_release_flow
        imports=import_release_flow(window.ctx.root/('import-flow-'+datetime.now().strftime('%Y%m%d%H%M%S%f')),output)
        results.extend(imports['screens'])
        info=dict(status='passed',platform=app.platformName(),screens=results,catalogue=window.ctx.catalogue.info(),data_root=str(window.ctx.root),transaction_flow=flow,import_flow=imports)
        (output/'smoke-result.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
        window.close()
        app.exit(0)
    except Exception:
        logging.exception('Smoke capture failed')
        (output/'smoke-result.json').write_text(json.dumps(dict(status='failed'),indent=2),encoding='utf-8')
        app.exit(1)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Mobile Desk offline phone trading')
    parser.add_argument('--data-dir',type=Path,help='Use an isolated writable data folder')
    parser.add_argument('--demo',action='store_true',help='Use a separate practice workspace with sample data')
    parser.add_argument('--smoke-test',type=Path,help='Capture application screens and exit; requires --data-dir')
    args=parser.parse_args(argv)
    if args.smoke_test and not args.data_dir:
        parser.error('--smoke-test requires an explicit isolated --data-dir')
    root=(args.data_dir or (data_root()/'Practice' if args.demo else data_root())).resolve()
    root.mkdir(parents=True,exist_ok=True)
    (root/'logs').mkdir(exist_ok=True)
    handler=RotatingFileHandler(root/'logs/mobile_desk.log',maxBytes=2_000_000,backupCount=5,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    app=QApplication(sys.argv[:1])
    app.setApplicationName('Mobile Desk')
    app.setOrganizationName('MobileDesk')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    lock=QLockFile(str(root/'mobile_desk.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None,'Mobile Desk is already open','Use the existing Mobile Desk window for this data folder.')
        return 1
    def exception_handler(kind,value,tb):
        logging.error('Unhandled application error',exc_info=(kind,value,tb))
        if args.smoke_test:
            app.exit(1)
        else:
            QMessageBox.warning(None,'Mobile Desk','The action could not be completed. Your posted records remain saved. Details are in the application log.')
    sys.excepthook=exception_handler
    try:
        logging.info('Application starting')
        ctx=Context(root)
        if args.demo:
            seed_demo(ctx)
        window=MainWindow(ctx)
        window.show()
        if args.smoke_test:
            QTimer.singleShot(300,lambda:smoke_capture(window,args.smoke_test))
        else:
            QTimer.singleShot(200,window.first_run)
        result=app.exec()
        logging.info('Application closed')
        return result
    except Exception:
        logging.exception('Startup failed')
        if not args.smoke_test:
            QMessageBox.critical(None,'Mobile Desk could not start','The application could not open its data. Keep the data folder intact and check the startup log:\n'+str(root/'logs/mobile_desk.log'))
        return 1
    finally:
        lock.unlock()


if __name__=='__main__':
    raise SystemExit(main())
