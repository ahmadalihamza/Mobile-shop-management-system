from pathlib import Path
import json
import logging
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QHBoxLayout,QLineEdit,QFileDialog,QMessageBox,QTabWidget
from mobile_desk.ui.common import label,button,confirm,DataTable
from mobile_desk.ui.people_money import RateDialog
from mobile_desk.database import audit
from mobile_desk.values import BusinessError
from mobile_desk import __version__
from mobile_desk.ui.security import OwnerSetupDialog,OwnerAuthorizationDialog,ResetDialog


class SettingsPage(QWidget):
    def __init__(self,host,ctx):
        super().__init__()
        self.host,self.ctx=host,ctx
        layout=QVBoxLayout(self)
        layout.setContentsMargins(26,22,26,20)
        layout.setSpacing(14)
        layout.addWidget(label('Settings','title'))
        tabs=QTabWidget()
        layout.addWidget(tabs,1)
        shop=QWidget()
        sl=QVBoxLayout(shop)
        form=QFormLayout()
        self.fields={}
        for key,title in [('shop_name','Shop name'),('shop_phone','Phone'),('shop_address','Address'),('invoice_prefix','Invoice prefix'),('next_invoice','Next invoice sequence')]:
            w=QLineEdit(ctx.db.setting(key))
            self.fields[key]=w
            form.addRow(title,w)
        sl.addLayout(form)
        sl.addWidget(button('Save shop settings',self.save,True))
        sl.addStretch()
        sl.addWidget(label('Mobile Desk '+__version__+'\nOffline phone trading · Quantity stock · PKR','subtitle',True))
        sl.addWidget(label('Data folder: '+str(ctx.root),'subtitle',True))
        sl.addWidget(button('Open user guide',host.open_guide))
        tabs.addTab(shop,'Shop')
        backup=QWidget()
        bl=QVBoxLayout(backup)
        bl.addWidget(label('Back up your shop records','section'))
        bl.addWidget(label('Save a backup to a USB drive or another disk. Each package includes your business records, settings, and current reference catalogue.','subtitle',True))
        bl.addWidget(button('Backup Database',self.backup,True))
        bl.addWidget(button('Restore Backup',self.restore))
        bl.addWidget(label('Restore checks the package first and saves a safety backup before replacing the current records.','subtitle',True))
        self.backup_folder=QLineEdit(ctx.db.setting('backup_folder'))
        self.backup_folder.setPlaceholderText('Optional preferred backup folder')
        bl.addWidget(self.backup_folder)
        bl.addWidget(button('Choose preferred backup folder',self.choose_backup_folder))
        bl.addStretch()
        tabs.addTab(backup,'Backup & Restore')
        cat=QWidget()
        cl=QVBoxLayout(cat)
        self.cat_info=label('','section',True)
        cl.addWidget(self.cat_info)
        cl.addWidget(label('Catalogue updates change reference information only. Your products, invoices and purchase costs remain as saved.','subtitle',True))
        cl.addWidget(button('Import Catalogue Update',self.import_catalogue,True))
        cl.addWidget(label('Use a Mobile Desk versioned JSON update package from a trusted source. Search runs entirely offline.','subtitle',True))
        cl.addStretch()
        tabs.addTab(cat,'Mobile Catalogue')
        rate=QWidget()
        rl=QVBoxLayout(rate)
        rl.addWidget(label('RMB → PKR rate history','section'))
        rl.addWidget(label('Rates suggest values for new batches. Finalized purchase lines keep their original rate.','subtitle',True))
        rl.addWidget(button('Add exchange rate',self.add_rate,True))
        self.rate_table=DataTable([('transaction_date','Date'),('rate','PKR for 1 RMB'),('notes','Notes')])
        rl.addWidget(self.rate_table)
        tabs.addTab(rate,'Exchange Rates')
        owner=QWidget()
        ol=QVBoxLayout(owner)
        ol.addWidget(label('Owner protection','section'))
        self.owner_info=label('','subtitle',True)
        ol.addWidget(self.owner_info)
        self.owner_button=button('Set owner password',self.configure_owner,True)
        ol.addWidget(self.owner_button)
        ol.addWidget(label('Reset All Business Data','section'))
        ol.addWidget(label('Use this to clear practice entries or start the shop completely fresh. Purchases, sales, stock, contacts, payments and opening balances are cleared. Shop details, account names, catalogue and owner credentials are kept. A verified safety backup is required before clearing.','subtitle',True))
        ol.addWidget(label('For a new month, keep your existing stock and balances and change the report dates. For one wrong entry, use Undo Last Entry or Undo selected entry.','notice',True))
        self.reset_button=button('Reset All Business Data',self.reset_business)
        self.reset_button.setObjectName('danger')
        ol.addWidget(self.reset_button)
        ol.addStretch()
        tabs.addTab(owner,'Owner & Reset')
        self.status=label('','subtitle',True)
        layout.addWidget(self.status)
        self.refresh()

    def refresh(self):
        # A cached settings page must not suggest an obsolete invoice sequence.
        sequence=self.fields['next_invoice']
        if not sequence.isModified():
            sequence.setText(self.ctx.db.setting('next_invoice'))
        info=self.ctx.catalogue.info() if self.ctx.catalogue else dict(count=0,brands=0,version='Unavailable')
        self.cat_info.setText(f"{info['count']:,} model references · {info['brands']} brands\nVersion {info['version']}")
        self.rate_table.populate(self.ctx.money.rates())
        configured=self.ctx.security.configured
        self.owner_button.setText('Change owner password' if configured else 'Set owner password')
        self.reset_button.setEnabled(configured)
        try:
            self.owner_info.setText('Owner: '+self.ctx.security.username+'. Reset and restore require the owner password.' if configured else 'The owner must set a username and password before reset or restore can be used. No default password is provided.')
        except BusinessError as e:
            self.owner_info.setText(str(e))
            self.reset_button.setEnabled(False)

    def guard(self,action):
        try:
            action()
        except BusinessError as e:
            QMessageBox.warning(self,'Could not complete',str(e))
        except Exception:
            logging.exception('Settings action failed')
            QMessageBox.warning(self,'Could not complete','The operation could not be completed. Check the selected file or folder and the application log.')

    def save(self):
        def action():
            self.ctx.money.save_settings(**{k:w.text() for k,w in self.fields.items()},setup_complete='1')
            for widget in self.fields.values():
                widget.setModified(False)
            self.status.setText('Shop settings saved.')
            self.host.setWindowTitle(self.ctx.db.setting('shop_name')+' — Mobile Desk')
        self.guard(action)

    def choose_backup_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Choose backup folder',self.backup_folder.text() or str(self.ctx.root/'backups'))
        if path:
            self.backup_folder.setText(path)
            self.guard(lambda:self.ctx.money.save_settings(backup_folder=path))

    def backup(self):
        folder=QFileDialog.getExistingDirectory(self,'Save backup to folder',self.backup_folder.text() or str(self.ctx.root/'backups'))
        if folder:
            self.guard(lambda:self.status.setText('Backup saved: '+str(self.ctx.backups.create(folder))))

    def restore(self):
        if not self.ctx.security.configured:
            QMessageBox.information(self,'Set owner credentials first','The owner must set a password in Settings → Owner & Reset before replacing shop records.')
            return
        path,_=QFileDialog.getOpenFileName(self,'Choose backup',str(self.ctx.root/'backups'),'Mobile Desk backup (*.mdbackup)')
        if not path:
            return
        def action():
            manifest=self.ctx.backups.inspect(path)
            if confirm(self,'Replace current shop records?',f"Backup created: {manifest['created_at']}\n\nThis replaces the current records. A safety backup will be saved automatically. Continue?"):
                authorization=OwnerAuthorizationDialog(self,self.ctx,'Authorize backup restore')
                if not authorization.exec():
                    return
                safety=self.ctx.backups.restore(path,**authorization.result_id)
                QMessageBox.information(self,'Restore complete','Records restored successfully.\nSafety backup: '+str(safety))
                self.host.reload_context()
        self.guard(action)

    def configure_owner(self):
        def action():
            if OwnerSetupDialog(self,self.ctx).exec():
                self.status.setText('Owner password saved. Keep the credentials safely.')
                self.refresh()
        self.guard(action)

    def reset_business(self):
        def action():
            dialog=ResetDialog(self,self.ctx)
            if dialog.exec():
                safety=dialog.result_id
                self.host.reload_context()
                QMessageBox.information(self.host,'Fresh start ready','All business records and balances are now empty. Shop settings and owner credentials were kept.\n\nEnter actual opening stock and balances before trading.\n\nTo recover the cleared records, use Restore Backup with your owner password.\nSafety backup: '+str(safety))
        self.guard(action)

    def import_catalogue(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose catalogue update','','Catalogue JSON (*.json)')
        if not path:
            return
        def action():
            if self.ctx.catalogue is None:
                raise BusinessError('The catalogue database needs recovery. Restore a valid backup or ask the administrator to preserve and replace the damaged catalogue file.')
            count=self.ctx.catalogue.import_file(path)
            with self.ctx.db.connect(write=True) as c:
                audit(c,'IMPORT','catalogue',self.ctx.catalogue.info()['version'])
            self.status.setText(f'Catalogue updated successfully: {count:,} records processed.')
            self.refresh()
        self.guard(action)

    def add_rate(self):
        if RateDialog(self,self.ctx).exec():
            self.refresh()
