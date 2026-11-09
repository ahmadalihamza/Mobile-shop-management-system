from decimal import Decimal
from html import escape
import logging
from pathlib import Path
import uuid
from PySide6.QtCore import QDate, Qt, QTimer, Signal
from PySide6.QtGui import QRegularExpressionValidator, QTextDocument, QPageSize
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (QWidget,QDialog,QLabel,QPushButton,QLineEdit,QComboBox,QDateEdit,QVBoxLayout,QHBoxLayout,QFormLayout,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QMessageBox,QFileDialog,QTextBrowser,QScrollArea)
from PySide6.QtPrintSupport import QPrinter,QPrintPreviewDialog
from mobile_desk.values import BusinessError, currency, money, today
from mobile_desk.paths import resource_path

STYLE = '''
* {font-family:"Segoe UI"; font-size:14px; color:#183b32;}
QMainWindow,QDialog {background:#f5f7f3;}
QWidget#sidebar {background:#173e34;}
QLabel#brand {color:#ffffff; font-size:25px; font-weight:700; padding:16px 12px;}
QLabel#sideNote {color:#b5d0c4; font-size:12px; padding:12px;}
QPushButton#nav {background:transparent; color:#d5e6dd; border:0; text-align:left; padding:14px 16px; border-radius:7px;}
QPushButton#nav:checked {background:#35614f; color:white; font-weight:600;}
QPushButton#nav:hover {background:#2b5547;}
QLabel#title {font-size:27px; font-weight:650; color:#173e34;}
QLabel#subtitle {color:#687e72; font-size:13px;}
QLabel#section {font-size:18px; font-weight:600;}
QLabel#metric {font-size:26px; font-weight:650;}
QLabel#error {color:#a33330; padding:5px;}
QLabel#notice {background:#fff0cc; color:#73541f; padding:12px; border-radius:6px;}
QFrame#card {background:#fff; border:1px solid #dfe7df; border-radius:9px;}
QPushButton {background:#fff; border:1px solid #cbdacf; padding:10px 15px; border-radius:6px; font-weight:550;}
QPushButton:hover {background:#edf3e9;}
QPushButton:disabled {color:#84968b; background:#edf0eb;}
QPushButton#primary {background:#256448; color:#fff; border-color:#256448;}
QPushButton#primary:hover {background:#194f37;}
QPushButton#danger {background:#a33330; color:#fff; border-color:#a33330;}
QPushButton#danger:hover {background:#842622;}
QLineEdit,QComboBox,QDateEdit,QSpinBox {background:#fff; border:1px solid #cbd8cd; border-radius:5px; padding:8px; min-height:22px; selection-background-color:#31664e;}
QLineEdit:focus,QComboBox:focus,QDateEdit:focus,QSpinBox:focus {border:1px solid #317454;}
QComboBox::drop-down {border:0; width:22px;}
QComboBox::down-arrow {image:url("DROPDOWN_IMAGE"); width:12px; height:8px;}
QTableWidget {background:#fff; alternate-background-color:#f8faf6; border:1px solid #dce5da; gridline-color:#edf1e8; selection-background-color:#dcebdd; selection-color:#173e34;}
QHeaderView::section {background:#eaf0e6; color:#47634f; border:0; padding:10px 8px; font-weight:600; font-size:12px;}
QTableWidget::item {padding:7px;}
QTableCornerButton::section {background:#eaf0e6; border:0;}
QScrollArea {border:0; background:transparent;}
QGroupBox {border:1px solid #dce5da; border-radius:6px; padding-top:18px; margin-top:12px;}
QGroupBox::title {subcontrol-origin:margin; left:12px; padding:0 6px; font-weight:600;}
QTabWidget::pane {border:0;}
QTabBar::tab {padding:11px 20px; background:#e8eee4; margin-right:3px;}
QTabBar::tab:selected {background:#fff; color:#256448; font-weight:600;}
QCheckBox {spacing:8px; padding:4px;}
QToolTip {color:#183b32; background:#fff; border:1px solid #cad9cd;}
'''.replace('DROPDOWN_IMAGE',resource_path('dropdown.svg').as_posix())


def label(value, name='', wrap=False):
    w=QLabel(str(value))
    w.setTextFormat(Qt.TextFormat.PlainText)
    w.setWordWrap(wrap)
    if name:
        w.setObjectName(name)
    return w


def trading_label(value):
    return {'POSTED':'Saved','VOID':'Voided','CHINA_IMPORT':'China / RMB','LOCAL':'Local','OPENING':'Opening stock','SALE_RECEIPT':'Paid at sale','CUSTOMER_PAYMENT':'Customer payment','PURCHASE_PAYMENT':'Supplier / purchase payment','RETURN_REFUND':'Customer refund'}.get(value,str(value).replace('_',' ').title())


def button(title, handler, primary=False):
    w=QPushButton(title.replace('&','&&'))
    w.setAutoDefault(False)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        w.setObjectName('primary')
    w.clicked.connect(handler)
    return w


def date_edit(value=None):
    w=QDateEdit(QDate.fromString(value or today(),'yyyy-MM-dd'))
    w.setCalendarPopup(True)
    w.setDisplayFormat('dd MMM yyyy')
    return w


def day(widget):
    return widget.date().toString('yyyy-MM-dd')


def combo(rows=(), label_key='name', optional=None, selected=None):
    w=QComboBox()
    w.setMinimumWidth(170)
    if optional is not None:
        w.addItem(optional,None)
    for r in rows:
        w.addItem(str(r[label_key]),r['id'])
    if selected is not None:
        w.setCurrentIndex(w.findData(selected))
    return w


def refresh_party_combo(widget, ctx, role, placeholder):
    """Refresh saved page filters without losing selection or emitting recursive refreshes."""
    selected=widget.currentData()
    rows=ctx.parties.search(role=role,limit=10000)
    options=[(placeholder,None)]+[(party_selection_name(r),r['id']) for r in rows]
    if options==[(widget.itemText(i),widget.itemData(i)) for i in range(widget.count())]:
        return
    prior=widget.blockSignals(True)
    try:
        widget.clear()
        for title,identity in options:
            widget.addItem(title,identity)
        widget.setCurrentIndex(max(0,widget.findData(selected)))
    finally:
        widget.blockSignals(prior)


def party_selection_name(row):
    """Distinguish pre-existing duplicate accounts without combining their ledgers."""
    if row.get('name_count',1)>1:
        details=row.get('phone') or row.get('address')
        return row['name']+' · '+(details+' · ' if details else '')+f"Account {row['id']}"
    return row['name']


def party_combo(ctx, role, placeholder, selected=None):
    rows=ctx.parties.search(role=role,limit=10000,active_only=True)
    for row in rows:
        row['selection_name']=party_selection_name(row)
    widget=combo(rows,'selection_name',optional=placeholder,selected=selected)
    widget.setMaxVisibleItems(12)
    widget.setToolTip('Select a saved contact. Use Choose from list to search by name or phone.')
    return widget


def select_saved_party(widget, ctx, identity):
    row=ctx.db.one('SELECT p.*,(SELECT COUNT(*) FROM parties other WHERE other.normalized_name=p.normalized_name) AS name_count FROM parties p WHERE id=?',(identity,))
    index=widget.findData(identity)
    if index<0:
        widget.addItem(party_selection_name(row),identity)
        index=widget.count()-1
    else:
        widget.setItemText(index,party_selection_name(row))
    widget.setCurrentIndex(index)


class AmountEdit(QLineEdit):
    def __init__(self, value='0', places=2):
        super().__init__(str(value))
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r'\d{0,10}(\.\d{0,'+str(places)+r'})?'),self))
        self.setMinimumWidth(105)

    def value(self):
        return self.text() or '0'

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            self.focusNextChild()
            event.accept()
            return
        super().keyPressEvent(event)


class DataTable(QTableWidget):
    def __init__(self, columns):
        super().__init__(0,len(columns))
        self.columns=columns
        self.data_rows=[]
        self.setHorizontalHeaderLabels([c[1] for c in columns])
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(42)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setMaximumSectionSize(420)

    def populate(self, rows):
        self.data_rows=list(rows)
        self.setRowCount(len(self.data_rows))
        for i,row in enumerate(self.data_rows):
            for j,col in enumerate(self.columns):
                value=row.get(col[0],'')
                display=col[2](value) if len(col)>2 and (value is not None or col[2] is currency) else ('' if value is None else str(value))
                item=QTableWidgetItem(display)
                item.setToolTip(display)
                if isinstance(value,(int,Decimal)):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                self.setItem(i,j,item)
        if self.rowCount():
            self.selectRow(0)

    def selected(self):
        i=self.currentRow()
        return self.data_rows[i] if 0<=i<len(self.data_rows) else None


class EntryDialog(QDialog):
    def __init__(self,parent,title,width=650):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(width,600)
        self.setMinimumWidth(min(width,620))
        self.key=str(uuid.uuid4())
        self.result_id=None
        self.layout=QVBoxLayout(self)
        self.layout.setContentsMargins(22,20,22,18)
        self.layout.setSpacing(12)
        self.layout.addWidget(label(title,'section'))
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        body=QWidget()
        self.body=QVBoxLayout(body)
        self.body.setContentsMargins(0,0,8,0)
        scroll.setWidget(body)
        self.layout.addWidget(scroll,1)
        self.error=label('','error',True)
        self.layout.addWidget(self.error)
        self.footer=QHBoxLayout()
        self.footer.addStretch()
        self.footer.addWidget(button('Cancel',self.reject))
        self.save_button=button('Save',self.commit,True)
        self.footer.addWidget(self.save_button)
        self.layout.addLayout(self.footer)
        self.form=QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setSpacing(10)
        self.body.addLayout(self.form)
        self.save_handler=None

    def field(self,title,widget):
        self.form.addRow(title,widget)
        return widget

    def commit(self):
        if not self.save_button.isEnabled():
            return
        self.save_button.setEnabled(False)
        try:
            self.result_id=self.save_handler()
            self.accept()
        except BusinessError as e:
            self.error.setText(str(e))
        except Exception:
            logging.exception('Could not save %s',self.windowTitle())
            self.error.setText('Could not save this entry. No partial transaction was posted. Please try again or check the application log.')
        finally:
            self.save_button.setEnabled(True)


class ListPage(QWidget):
    def __init__(self,title,subtitle,columns,loader,actions=(),date_filter=False):
        super().__init__()
        self.loader=loader
        self.offset=0
        self.limit=100
        self.layout=QVBoxLayout(self)
        self.layout.setContentsMargins(26,22,26,20)
        self.layout.setSpacing(14)
        self.layout.addWidget(label(title,'title'))
        self.layout.addWidget(label(subtitle,'subtitle',True))
        self.actions=QHBoxLayout()
        for i,(name,handler) in enumerate(actions):
            self.actions.addWidget(button(name,handler,i==0))
        self.actions.addStretch()
        self.layout.addLayout(self.actions)
        self.filters=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText('Search…')
        self.search.setClearButtonEnabled(True)
        self.filters.addWidget(self.search,1)
        self.start=self.end=None
        if date_filter:
            self.start=date_edit(today()[:8]+'01')
            self.end=date_edit()
            self.filters.addWidget(label('From'))
            self.filters.addWidget(self.start)
            self.filters.addWidget(label('To'))
            self.filters.addWidget(self.end)
            self.start.dateChanged.connect(self.reset)
            self.end.dateChanged.connect(self.reset)
        self.layout.addLayout(self.filters)
        self.table=DataTable(columns)
        self.layout.addWidget(self.table,1)
        footer=QHBoxLayout()
        self.note=label('','subtitle')
        footer.addWidget(self.note,1)
        self.previous=button('Previous',lambda:self.page(-1))
        self.next=button('Next',lambda:self.page(1))
        footer.addWidget(self.previous)
        footer.addWidget(self.next)
        self.layout.addLayout(footer)
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.reset)
        self.search.textChanged.connect(lambda:self.timer.start())

    def reset(self,*args):
        self.offset=0
        self.refresh()

    def page(self,direction):
        self.offset=max(0,self.offset+direction*self.limit)
        self.refresh()

    def refresh(self):
        try:
            rows=self.loader(self)
            more=len(rows)>self.limit
            rows=rows[:self.limit]
            self.table.populate(rows)
            self.note.setText(f'{self.offset+1}–{self.offset+len(rows)}' if rows else 'No records in this view. Add an entry or change the filters.')
            self.previous.setEnabled(self.offset>0)
            self.next.setEnabled(more)
        except Exception:
            logging.exception('Could not refresh list')
            self.note.setText('Could not load this list. Check the application log.')


def confirm(parent,title,message):
    return QMessageBox.question(parent,title,message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes


def printable_table(title,columns,rows,subtitle=''):
    headings=''.join('<th>'+escape(c[1])+'</th>' for c in columns)
    body=[]
    for r in rows:
        values=[]
        for col in columns:
            v=r.get(col[0],'')
            s=col[2](v) if len(col)>2 and (v is not None or col[2] is currency) else ('' if v is None else str(v))
            values.append('<td>'+escape(s)+'</td>')
        body.append('<tr>'+''.join(values)+'</tr>')
    return '<html><head><style>body{font-family:Segoe UI;font-size:10pt;color:#173e34}h1{font-size:20pt}table{border-collapse:collapse;width:100%}th{background:#e7eee5;text-align:left}td,th{padding:7px;border-bottom:1px solid #ddd}p{white-space:pre-wrap}</style></head><body><h1>'+escape(title)+'</h1><p>'+escape(subtitle)+'</p><table><thead><tr>'+headings+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></body></html>'


def show_print(parent,title,html):
    d=QDialog(parent)
    d.setWindowTitle(title)
    d.resize(850,700)
    layout=QVBoxLayout(d)
    browser=QTextBrowser()
    browser.setHtml(html)
    layout.addWidget(browser)
    bar=QHBoxLayout()
    def preview():
        printer=QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        dialog=QPrintPreviewDialog(printer,d)
        dialog.paintRequested.connect(browser.document().print_)
        dialog.exec()
    def pdf():
        path,_=QFileDialog.getSaveFileName(d,'Save PDF',title+'.pdf','PDF (*.pdf)')
        if path:
            printer=QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            browser.document().print_(printer)
    bar.addWidget(button('Print / Preview',preview,True))
    bar.addWidget(button('Save PDF',pdf))
    bar.addStretch()
    bar.addWidget(button('Close',d.accept))
    layout.addLayout(bar)
    d.exec()
