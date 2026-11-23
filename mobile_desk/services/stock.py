from mobile_desk.values import BusinessError, timestamp, weighted_average


def chronological(c, product_id: int, day: str):
    """Do not silently re-cost past sales when inserting dated stock movements."""
    last = c.execute('SELECT MAX(m.transaction_date) FROM stock_movements m JOIN purchase_items p ON p.id=m.purchase_item_id WHERE p.product_id=?', (product_id,)).fetchone()[0]
    if last and day < last:
        raise BusinessError(f'This product already has stock activity dated {last}. Use that date or later; earlier entries need an administrator-reviewed chronological migration.')


def move(c, lot_id: int, day: str, qty: int, kind: str, reference: int):
    c.execute('INSERT INTO stock_movements(purchase_item_id,transaction_date,quantity,kind,reference_id,created_at) VALUES(?,?,?,?,?,?)', (lot_id, day, qty, kind, reference, timestamp()))


def fifo_lots(c, product_id, day):
    return c.execute("SELECT id,remaining_quantity,landed_unit_cost FROM lot_stock WHERE product_id=? AND status='POSTED' AND transaction_date<=? AND remaining_quantity>0 ORDER BY transaction_date,id", (product_id, day))


def allocate(c, sale_item_id: int, product_id: int, day: str, qty: int) -> int:
    lots = fifo_lots(c,product_id,day).fetchall()
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

    def estimate_fifo(self, day, lines):
        """Read-only preview using the same lot order and chronology as posting."""
        demand = {}
        for line in lines:
            identity = line['product_id']
            demand[identity] = demand.get(identity,0) + line['quantity']
        total = 0
        with self.db.connect() as c:
            c.execute('BEGIN')
            for identity, remaining in demand.items():
                try:
                    chronological(c,identity,day)
                except BusinessError:
                    return None
                for lot in fifo_lots(c,identity,day):
                    take = min(remaining,lot['remaining_quantity'])
                    total += take * lot['landed_unit_cost']
                    remaining -= take
                    if not remaining:
                        break
                if remaining:
                    return None
        return total

    def current(self, query='', limit=200, offset=0, *, product_id=None):
        from mobile_desk.values import normalize
        clauses = ['1=1']
        params = []
        if product_id is not None:
            clauses.append('p.id=?')
            params.append(product_id)
        for token in normalize(query).split():
            clauses.append("(instr(replace(p.normalized_search_name,' ',''),?)>0 OR EXISTS(SELECT 1 FROM product_aliases a WHERE a.product_id=p.id AND instr(replace(a.normalized_alias,' ',''),?)>0))")
            params.extend([token,token])
        rows = self.db.rows("""
            WITH page AS MATERIALIZED (
                SELECT p.id,p.custom_name,p.active FROM products p WHERE """ + ' AND '.join(clauses) + """
                ORDER BY p.custom_name,p.id LIMIT ? OFFSET ?
            ), lots AS MATERIALIZED (
                SELECT l.* FROM page p CROSS JOIN lot_stock l WHERE l.product_id=p.id
            )
            SELECT p.*,COALESCE(SUM(l.remaining_quantity),0) quantity,
                COALESCE(SUM(l.remaining_quantity*l.landed_unit_cost),0) value,
                COALESCE(SUM(CASE WHEN l.inventory_status='REVIEW'
                    AND (l.source_remaining_quantity IS NULL OR l.source_remaining_quantity>0)
                    AND NOT EXISTS(SELECT 1 FROM inventory_confirmations ic WHERE ic.purchase_item_id=l.id)
                    THEN l.quantity ELSE 0 END),0) unverified_purchase_quantity
            FROM page p LEFT JOIN lots l ON l.product_id=p.id
            GROUP BY p.id ORDER BY p.custom_name,p.id
        """, (*params, limit, offset))
        from mobile_desk.services.products import ProductService
        averages=ProductService(self.db).purchase_averages([row['id'] for row in rows])
        for row in rows:
            row.update(averages[row['id']])
            row['available_average'] = weighted_average(row['value'], row['quantity'])
        return rows

    def lots(self, product_id):
        return self.db.rows("""
            SELECT l.*,b.supplier_snapshot,b.shipment_status,b.received_date,
                COALESCE(s.carry_basis,'PER_UNIT') carry_basis,
                s.carry_input,COALESCE(s.total_carry_cost,l.quantity*l.additional_cost_per_unit) cargo,
                (SELECT COALESCE(SUM(quantity),0) FROM purchase_return_items WHERE purchase_item_id=l.id) supplier_returned,
                -(SELECT COALESCE(SUM(quantity),0) FROM stock_movements
                  WHERE purchase_item_id=l.id AND kind IN ('SALE','VOID_SALE','RETURN','VOID_RETURN')) sold
            FROM lot_stock l JOIN purchase_batches b ON b.id=l.purchase_batch_id
            LEFT JOIN purchase_stacks s ON s.id=l.stack_id
            WHERE l.product_id=? ORDER BY l.transaction_date,l.id
        """, (product_id,))

    def incoming(self):
        return self.db.one("""
            SELECT COALESCE(SUM(i.quantity-(SELECT COALESCE(SUM(r.quantity),0)
                FROM purchase_return_items r WHERE r.purchase_item_id=i.id)),0) pieces
            FROM purchase_batches b JOIN purchase_items i ON i.purchase_batch_id=b.id
            WHERE b.status='POSTED' AND b.shipment_status='IN_TRANSIT'
        """)['pieces']

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
