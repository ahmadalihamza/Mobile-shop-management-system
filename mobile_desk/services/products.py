from decimal import Decimal, ROUND_HALF_UP
from mobile_desk.database import Database, audit
from mobile_desk.values import BusinessError, normalize, text, timestamp


class ProductService:
    def __init__(self, db: Database):
        self.db = db

    def save(self, *, product_id=None, custom_name='', catalogue_model_id=None, brand='', model='', ram='', storage='', color='', variant='', aliases=(), active=True) -> int:
        fields = {key: text(value, key.title(), limit=150) for key, value in dict(brand=brand, model=model, ram=ram, storage=storage, color=color, variant=variant).items()}
        if not custom_name.strip():
            capacity = '/'.join(v for v in (fields['ram'], fields['storage']) if v)
            custom_name = ' '.join(v for v in (fields['brand'], fields['model'], capacity, fields['color'], fields['variant']) if v)
        name = text(custom_name, 'Product name', True)
        with self.db.connect(write=True) as c:
            values = (catalogue_model_id, *fields.values(), name, normalize(name + ' ' + ' '.join(fields.values())), int(active))
            if product_id:
                if not c.execute('SELECT 1 FROM products WHERE id=?', (product_id,)).fetchone():
                    raise BusinessError('Product not found.')
                c.execute('UPDATE products SET catalogue_model_id=?,brand=?,model=?,ram=?,storage=?,color=?,variant=?,custom_name=?,normalized_search_name=?,active=?,updated_at=? WHERE id=?', (*values, timestamp(), product_id))
            else:
                product_id = c.execute('INSERT INTO products(catalogue_model_id,brand,model,ram,storage,color,variant,custom_name,normalized_search_name,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (*values, timestamp(), timestamp())).lastrowid
            c.execute('DELETE FROM product_aliases WHERE product_id=?', (product_id,))
            for alias in aliases:
                alias = text(alias, 'Alias')
                if alias:
                    c.execute('INSERT OR IGNORE INTO product_aliases(product_id,alias,normalized_alias) VALUES(?,?,?)', (product_id, alias, normalize(alias)))
            audit(c, 'SAVE', 'product', product_id)
            return product_id

    def search(self, query='', active_only=True, limit=100, offset=0) -> list[dict]:
        clauses, args = ['1=1'], []
        if active_only:
            clauses.append('p.active=1')
        for token in normalize(query).split():
            clauses.append("(instr(replace(p.normalized_search_name,' ',''),?)>0 OR EXISTS(SELECT 1 FROM product_aliases a WHERE a.product_id=p.id AND instr(replace(a.normalized_alias,' ',''),?)>0))")
            args.extend([token, token])
        rows = self.db.rows('SELECT p.*,COALESCE((SELECT SUM(remaining_quantity) FROM lot_stock WHERE product_id=p.id),0) AS stock FROM products p WHERE ' + ' AND '.join(clauses) + ' ORDER BY p.active DESC,p.custom_name LIMIT ? OFFSET ?', (*args, limit, offset))
        averages = self.purchase_averages(row['id'] for row in rows)
        for row in rows:
            row.update(averages[row['id']])
        return rows

    def get(self, identity):
        row = self.db.one('SELECT * FROM products WHERE id=?', (identity,))
        if row:
            row.update(self.purchase_averages([row['id']])[row['id']])
        return row

    def purchase_averages(self, product_ids=None) -> dict[int, dict]:
        """Weighted landed acquisition cost, in paisa, across net purchase history.

        Every posted acquisition, including opening and in-transit stock,
        contributes its original landed PKR cost. Supplier returns remove the
        returned pieces at that lot's original cost; cancelled batches contribute
        nothing. Sales and customer returns do not change the purchase average or
        reprice FIFO allocations.

        A sold-out product retains its purchase average. A product never purchased,
        or with all purchases cancelled/returned, has no average (None).
        """
        params = ()
        clause = ''
        if product_ids is not None:
            params = tuple(dict.fromkeys(product_ids))
            if not params:
                return {}
            clause = 'WHERE p.id IN (' + ','.join('?' for _ in params) + ')'
        rows = self.db.rows('''
            WITH supplier_returns AS (
                SELECT purchase_item_id,SUM(quantity) returned_quantity
                FROM purchase_return_items
                GROUP BY purchase_item_id
            ), acquisitions AS (
                SELECT i.product_id,i.quantity-COALESCE(r.returned_quantity,0) quantity,
                       i.landed_unit_cost
                FROM purchase_items i
                JOIN purchase_batches b ON b.id=i.purchase_batch_id
                LEFT JOIN supplier_returns r ON r.purchase_item_id=i.id
                WHERE b.status='POSTED'
            )
            SELECT p.id,COALESCE(SUM(a.quantity),0) purchased_quantity,
                   COALESCE(SUM(a.quantity*a.landed_unit_cost),0) purchase_cost
            FROM products p LEFT JOIN acquisitions a ON a.product_id=p.id
            ''' + clause + ' GROUP BY p.id', params)
        return {
            row['id']: dict(
                purchased_quantity=row['purchased_quantity'],
                purchase_cost=row['purchase_cost'],
                average_purchase_price=int((Decimal(row['purchase_cost']) /
                    row['purchased_quantity']).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                    if row['purchased_quantity'] else None,
            )
            for row in rows
        }

    def aliases(self, identity):
        return [r['alias'] for r in self.db.rows('SELECT alias FROM product_aliases WHERE product_id=?', (identity,))]
