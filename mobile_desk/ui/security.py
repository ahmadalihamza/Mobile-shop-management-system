"""Small, explicit dialogs for owner setup, authorization and fresh starts."""
from PySide6.QtWidgets import QLineEdit
from mobile_desk.ui.common import EntryDialog, label
from mobile_desk.values import BusinessError


def password_field():
    widget = QLineEdit()
    widget.setEchoMode(QLineEdit.EchoMode.Password)
    widget.setMaxLength(1024)
    return widget


class OwnerSetupDialog(EntryDialog):
    def __init__(self, parent, ctx):
        configured = ctx.security.configured
        super().__init__(parent, 'Change owner password' if configured else 'Set owner password', 660)
        self.username = self.field('Owner username', QLineEdit(ctx.security.username if configured else 'owner'))
        self.username.setReadOnly(configured)
        self.current = self.field('Current password', password_field()) if configured else None
        self.password = self.field('New password', password_field())
        self.confirmation = self.field('Confirm new password', password_field())
        self.body.addWidget(label('The owner should set this personally before staff use the software. Use at least 8 characters and keep the credentials safely. There is no default password. Reset and backup restore require these credentials.','subtitle',True))
        self.save_handler = lambda: ctx.security.set_password(self.username.text(), self.password.text(),
            self.confirmation.text(), current_password=self.current.text() if self.current else None)


class OwnerAuthorizationDialog(EntryDialog):
    def __init__(self, parent, ctx, title='Owner authorization'):
        super().__init__(parent, title, 650)
        self.username = self.field('Owner username', QLineEdit(ctx.security.username))
        self.password = self.field('Owner password', password_field())
        self.body.addWidget(label('Enter the owner credentials to replace current shop records.','subtitle',True))
        self.save_button.setText('Authorize')
        def authorize():
            credentials = dict(username=self.username.text(), password=self.password.text())
            ctx.security.authorize(**credentials)
            return credentials
        self.save_handler = authorize


class ResetDialog(EntryDialog):
    def __init__(self, parent, ctx):
        super().__init__(parent, 'Reset All Business Data', 720)
        counts = ' · '.join(f'{title}: {count:,}' for title, count in ctx.reset.preview().items())
        self.body.insertWidget(0, label('This clears ALL business records, including stock, purchases, sales, contacts, payments, returns, expenses and opening balances. The invoice sequence starts again at 1.','notice',True))
        self.body.insertWidget(1, label(counts,'subtitle',True))
        self.body.insertWidget(2, label('Shop details, cash/bank account names, the reference catalogue and owner credentials are kept. All account balances become zero. A safety backup is saved automatically before clearing.','subtitle',True))
        self.body.insertWidget(3, label('A new month does not need a reset. Use report dates for monthly figures and keep your stock and unpaid balances.','subtitle',True))
        self.username = self.field('Owner username', QLineEdit(ctx.security.username))
        self.password = self.field('Owner password', password_field())
        self.confirmation = self.field('Type RESET to confirm', QLineEdit())
        self.save_button.setText('Back Up and Reset All Data')
        self.save_button.setObjectName('danger')
        self.save_handler = lambda: ctx.reset.reset(self.username.text(), self.password.text(), self.confirmation.text())


class UndoDialog(EntryDialog):
    def __init__(self, parent, ctx, entry):
        from mobile_desk.values import currency
        super().__init__(parent, 'Undo Last Entry', 650)
        self.body.insertWidget(0, label(f"{entry['kind'].title()} · {entry['reference']} · {entry['transaction_date']}\nPKR {currency(entry['amount'])}",'section',True))
        self.body.insertWidget(1, label('This reverses this saved entry and its attached stock/payments. The original remains marked Voided in history. Later on-account payments remain; enter a corrected bill if needed.','subtitle',True))
        self.username = self.field('Owner username',QLineEdit(ctx.security.username)) if entry['kind']=='purchase' else None
        self.password = self.field('Owner password',password_field()) if entry['kind']=='purchase' else None
        if entry['kind']=='purchase':
            self.body.addWidget(label('Owner authorization is required. Use this only to correct a mistaken entry. For a real shipment return and supplier refund, use Purchases → Stock Return / Purchase Cancellation.','notice',True))
        self.save_button.setText('Undo This Entry')
        self.save_handler = lambda: ctx.corrections.undo_latest(entry['audit_id'],**(dict(username=self.username.text(),password=self.password.text()) if self.username else {}))
