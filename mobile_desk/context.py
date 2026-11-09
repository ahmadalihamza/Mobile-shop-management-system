from pathlib import Path
import logging
from mobile_desk.paths import prepare, resource_path
from mobile_desk.database import Database
from mobile_desk.catalogue import Catalogue
from mobile_desk.services.products import ProductService
from mobile_desk.services.parties import PartyService
from mobile_desk.services.purchases import PurchaseService
from mobile_desk.services.sales import SaleService
from mobile_desk.services.returns import ReturnService
from mobile_desk.services.money import MoneyService
from mobile_desk.services.stock import StockService
from mobile_desk.services.reports import ReportService
from mobile_desk.services.backup import BackupService, recover_interrupted_restore, reject_imported_history
from mobile_desk.services.activity import ActivityService
from mobile_desk.services.security import SecurityService
from mobile_desk.services.reset import ResetService
from mobile_desk.services.corrections import CorrectionService
from mobile_desk.services.purchase_returns import PurchaseReturnService


class Context:
    def __init__(self, root: Path, install_catalogue=True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        recover_interrupted_restore(self.root)
        prepare(self.root)
        self.db = Database(self.root/'data/mobile_desk.db')
        reject_imported_history(self.db.path)
        self.products = ProductService(self.db)
        self.parties = PartyService(self.db)
        self.security = SecurityService(self.root)
        self.purchases = PurchaseService(self.db,self.security)
        self.purchase_returns = PurchaseReturnService(self.db,self.security)
        self.sales = SaleService(self.db)
        self.returns = ReturnService(self.db)
        self.money = MoneyService(self.db)
        self.stock = StockService(self.db)
        self.reports = ReportService(self.db)
        self.activity = ActivityService(self.db)
        self.backups = BackupService(self.root)
        self.reset = ResetService(self.root, self.db)
        self.corrections = CorrectionService(self)
        if not self.money.accounts():
            self.money.account('Cash', 'CASH')
        self.catalogue_warning = ''
        self.catalogue = None
        try:
            self.catalogue = Catalogue(self.root/'data/mobile_catalogue.db')
            if install_catalogue and self.catalogue.info()['count'] == 0:
                bundled = resource_path('mobile_catalogue.json')
                if bundled.exists():
                    self.catalogue.import_file(bundled)
                else:
                    self.catalogue_warning = 'The reference catalogue is missing. Add products manually or import a catalogue update in Settings.'
        except Exception:
            logging.exception('Catalogue initialization failed')
            self.catalogue_warning = 'The reference catalogue could not be opened. Shop products and transactions remain available. Restore or repair the catalogue in Settings.'
