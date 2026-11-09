from mobile_desk.values import BusinessError, timestamp


def chronological(c, product_id: int, day: str):
    """Do not silently re-cost past sales when inserting dated stock movements."""
    last = c.execute('SELECT MAX(m.transaction_date) FROM stock_movements m JOIN purchase_items p ON p.id=m.purchase_item_id WHERE p.product_id=?', (product_id,)).fetchone()[0]
    if last and day < last:
        raise BusinessError(f'This product already has stock activity dated {last}. Use that date or later; earlier entries need an administrator-reviewed chronological migration.')


def move(c, lot_id: int, day: str, qty: int, kind: str, reference: int):
    c.execute('INSERT INTO stock_movements(purchase_item_id,transaction_date,quantity,kind,reference_id,created_at) VALUES(?,?,?,?,?,?)', (lot_id, day, qty, kind, reference, timestamp()))


def allocate(c, sale_item_id: int, product_id: int, day: str, qty: int) -> int:
    lots = c.execute("SELECT * FROM lot_stock WHERE product_id=? AND status='POSTED' AND transaction_date<=? AND remaining_quantity>0 ORDER BY transaction_date,id", (product_id, day)).fetchall()
    left, cost = qty, 0
    for lot in lots:
        take = min(left, lot['remaining_quantity'])
        if not take:
            break
        c.execute('INSERT INTO stock_allocations(sale_item_id,purchase_item_id,quantity,unit_cost) VALUES(?,?,?,?)', (sale_item_id, lot['id'], take, lot['landed_unit_cost']))
        move(c, lot['id'], day, -take, 'SALE', sale_item_id)
        cost += take * lot['landed_unit_cost']
        left -= take
    if left:
        name = c.execute('SELECT custom_name FROM products WHERE id=?', (product_id,)).fetchone()[0]
        raise BusinessError(f'Not enough stock for {name}. Available: {qty-left}; requested: {qty}. No sale was posted.')
    return cost


class StockService:
    def __init__(self, db):
        self.db = db

    def current(self, query='', limit=200, offset=0):
        from mobile_desk.values import normalize
        clauses = ['1=1']
        params = []
        for token in normalize(query).split():
            clauses.append("(instr(replace(p.normalized_search_name,' ',''),?)>0 OR EXISTS(SELECT 1 FROM product_aliases a WHERE a.product_id=p.id AND instr(replace(a.normalized_alias,' ',''),?)>0))")
            params.extend([token,token])
        rows=self.db.rows("SELECT p.id,p.custom_name,p.active,COALESCE(SUM(l.remaining_quantity),0) AS quantity,COALESCE(SUM(l.remaining_quantity*l.landed_unit_cost),0) AS value,COALESCE(SUM(CASE WHEN l.inventory_status='REVIEW' AND (l.source_remaining_quantity IS NULL OR l.source_remaining_quantity>0) AND NOT EXISTS(SELECT 1 FROM inventory_confirmations ic WHERE ic.purchase_item_id=l.id) THEN l.quantity ELSE 0 END),0) AS unverified_purchase_quantity FROM products p LEFT JOIN lot_stock l ON l.product_id=p.id WHERE " + ' AND '.join(clauses) + ' GROUP BY p.id ORDER BY p.custom_name LIMIT ? OFFSET ?', (*params, limit, offset))
        from mobile_desk.services.products import ProductService
        averages=ProductService(self.db).purchase_averages([row['id'] for row in rows])
        for row in rows:
            row.update(averages[row['id']])
        return rows

    def lots(self, product_id):
        return self.db.rows('SELECT * FROM lot_stock WHERE product_id=? ORDER BY transaction_date,id', (product_id,))

    def totals(self):
        return self.db.one('SELECT COALESCE(SUM(remaining_quantity),0) AS quantity,COALESCE(SUM(remaining_quantity*landed_unit_cost),0) AS value FROM lot_stock')

    def review_lots(self):
        return self.db.rows("SELECT l.*,p.custom_name,COALESCE((SELECT counted_quantity FROM inventory_confirmations i WHERE i.purchase_item_id=l.id ORDER BY id DESC LIMIT 1),NULL) last_count FROM lot_stock l JOIN products p ON p.id=l.product_id WHERE l.inventory_status='REVIEW' AND (l.source_remaining_quantity IS NULL OR l.source_remaining_quantity>0 OR l.remaining_quantity>0) ORDER BY l.reference,l.id")

    def confirm_count(self,lot_id,day,counted_quantity,reason=''):
        from mobile_desk.values import business_date,quantity,text,decimal
        from mobile_desk.database import audit
        business_date(day)
        counted=int(decimal(counted_quantity,'Counted quantity',places=0))
        reason=text(reason,'Action details',limit=2000) or 'Stock count confirmed'
        with self.db.connect(write=True) as c:
            lot=c.execute("SELECT * FROM lot_stock WHERE id=? AND status='POSTED' AND inventory_status='REVIEW'",(lot_id,)).fetchone()
            if not lot:
                raise BusinessError('Choose a historical cost lot awaiting stock verification.')
            if lot['source_remaining_quantity']==0 and not lot['remaining_quantity']:
                raise BusinessError('This source lot is already fully sold. Record actual returned or newly purchased goods separately.')
            if counted>lot['quantity']:
                raise BusinessError('Count exceeds this source purchase lot. Enter additional purchased stock as a separate batch.')
            if day<lot['transaction_date']:
                raise BusinessError('Count date cannot precede the purchase availability date.')
            chronological(c,lot['product_id'],day)
            identity=c.execute('INSERT INTO inventory_confirmations(purchase_item_id,transaction_date,counted_quantity,previous_quantity,reason,created_at) VALUES(?,?,?,?,?,?)',
                (lot_id,day,counted,lot['remaining_quantity'],reason,timestamp())).lastrowid
            change=counted-lot['remaining_quantity']
            if change:
                move(c,lot_id,day,change,'VERIFIED_COUNT',identity)
            audit(c,'VERIFY_STOCK','purchase_item',lot_id,reason)
            return identity
