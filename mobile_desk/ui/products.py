from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QCheckBox,QGridLayout,QWidget
from mobile_desk.ui.common import EntryDialog,DataTable,button,label


class ProductDialog(EntryDialog):
    def __init__(self,parent,ctx,product=None,catalogue=None):
        super().__init__(parent,'Edit Shop Product' if product else 'Add Shop Product',820)
        self.ctx=ctx
        self.product=product
        self.catalogue_id=product.get('catalogue_model_id') if product else None
        self.resize(820,740)
        self.catalogue_area=QWidget()
        cat_layout=QVBoxLayout(self.catalogue_area)
        cat_layout.setContentsMargins(0,0,0,0)
        line=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText('Find a phone in the offline catalogue… e.g. 15 pro, a55')
        line.addWidget(self.search,1)
        line.addWidget(button('+ Add Product Manually',self.manual))
        cat_layout.addLayout(line)
        self.results=DataTable([('brand','Brand'),('model_name','Model'),('release_year','Year')])
        self.results.setMaximumHeight(200)
        cat_layout.addWidget(self.results)
        cat_layout.addWidget(button('Use selected model',self.use_selected))
        self.body.insertWidget(0,self.catalogue_area)
        self.fields={}
        self.name=self.field('Product name',QLineEdit(product['custom_name'] if product else ''))
        self.name.setPlaceholderText('Use any useful name, including variant or condition')
        self.preview=label('','subtitle',True)
        self.body.addWidget(self.preview)
        self.details_area=QWidget()
        details_layout=QVBoxLayout(self.details_area)
        details_layout.setContentsMargins(0,0,0,0)
        grid=QGridLayout()
        for i,key in enumerate(('brand','model','ram','storage','color','variant')):
            w=QLineEdit(str(product.get(key,'') if product else ''))
            w.setPlaceholderText('Optional')
            self.fields[key]=w
            grid.addWidget(label(key.upper() if key=='ram' else key.title()),i//2*2,i%2)
            grid.addWidget(w,i//2*2+1,i%2)
            w.textChanged.connect(self.update_preview)
        details_layout.addLayout(grid)
        alias_row=QHBoxLayout()
        self.aliases=QLineEdit('; '.join(ctx.products.aliases(product['id'])) if product else '')
        alias_row.addWidget(label('Other search names'))
        alias_row.addWidget(self.aliases)
        details_layout.addLayout(alias_row)
        self.detail_toggle=QCheckBox('Brand, model and optional variant details')
        self.detail_toggle.toggled.connect(self.details_area.setVisible)
        self.body.addWidget(self.detail_toggle)
        self.body.addWidget(self.details_area)
        self.details_area.hide()
        self.aliases.setPlaceholderText('Separate aliases with semicolons')
        self.active=self.field('Available for new entries',QCheckBox('Active product'))
        self.active.setChecked(bool(product['active']) if product else True)
        self.name.textChanged.connect(self.update_preview)
        self.results.cellDoubleClicked.connect(lambda:self.use_selected())
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.find)
        self.search.textChanged.connect(lambda:self.timer.start())
        self.save_handler=self.save
        if catalogue:
            self.use_model(catalogue)
        elif product:
            self.catalogue_area.hide()
            self.detail_toggle.setChecked(True)
            self.update_preview()
        else:
            self.find()
            self.search.setFocus()

    def find(self):
        self.results.populate(self.ctx.catalogue.search(self.search.text(),50) if self.ctx.catalogue else [])

    def manual(self):
        self.catalogue_id=None
        self.catalogue_area.hide()
        self.detail_toggle.setChecked(False)
        self.name.setFocus()

    def use_selected(self):
        row=self.results.selected()
        if row:
            self.use_model(row)

    def use_model(self,row):
        self.catalogue_id=row['id']
        self.fields['brand'].setText(row['brand'])
        self.fields['model'].setText(row['model_name'])
        self.catalogue_area.hide()
        self.detail_toggle.setChecked(True)
        self.fields['ram'].setFocus()
        self.update_preview()

    def update_preview(self):
        parts={key:w.text().strip() for key,w in self.fields.items()}
        capacity='/'.join(x for x in (parts['ram'],parts['storage']) if x)
        built=' '.join(x for x in (parts['brand'],parts['model'],capacity,parts['color'],parts['variant']) if x)
        self.preview.setText('Display name: '+(self.name.text().strip() or built or 'Enter a name or brand and model'))

    def save(self):
        return self.ctx.products.save(product_id=self.product['id'] if self.product else None,custom_name=self.name.text(),catalogue_model_id=self.catalogue_id,aliases=self.aliases.text().split(';'),active=self.active.isChecked(),**{key:w.text() for key,w in self.fields.items()})


class ProductPicker(QDialog):
    def __init__(self,parent,ctx):
        super().__init__(parent)
        self.ctx=ctx
        self.product=None
        self.setWindowTitle('Choose Shop Product')
        self.resize(800,570)
        layout=QVBoxLayout(self)
        layout.addWidget(label('Choose Shop Product','section'))
        layout.addWidget(label('Your shop products appear here. Add a product to search the worldwide catalogue.','subtitle',True))
        bar=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText('Search product name, model or alias…')
        bar.addWidget(self.search,1)
        bar.addWidget(button('+ Add New Product',self.add,True))
        layout.addLayout(bar)
        self.table=DataTable([('custom_name','Shop product'),('stock','Available pieces')])
        layout.addWidget(self.table,1)
        self.table.cellDoubleClicked.connect(self.choose)
        foot=QHBoxLayout()
        foot.addStretch()
        foot.addWidget(button('Cancel',self.reject))
        foot.addWidget(button('Add selected product',self.choose,True))
        layout.addLayout(foot)
        self.search.textChanged.connect(self.refresh)
        self.search.returnPressed.connect(self.choose)
        self.refresh()
        self.search.setFocus()

    def refresh(self):
        self.table.populate(self.ctx.products.search(self.search.text(),limit=100))

    def choose(self,*args):
        self.product=self.table.selected()
        if self.product:
            self.accept()

    def add(self):
        d=ProductDialog(self,self.ctx)
        if d.exec():
            self.product=self.ctx.products.get(d.result_id)
            self.accept()
