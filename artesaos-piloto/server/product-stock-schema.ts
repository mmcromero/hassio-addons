/** B4: estoque físico sem inferir quantidades dos cadastros existentes. */
export const productStockSql=`
CREATE TABLE stock_locations(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('central','partner','session')),active INTEGER NOT NULL DEFAULT 1);
INSERT INTO stock_locations VALUES('central','Em minha posse','central',1);
CREATE TABLE stock_items(id TEXT PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),kind TEXT NOT NULL CHECK(kind IN ('own','client')),order_id TEXT,prices TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,CHECK((kind='own' AND order_id IS NULL) OR (kind='client' AND order_id IS NOT NULL)));
CREATE UNIQUE INDEX stock_own_product ON stock_items(product_id) WHERE kind='own';
CREATE UNIQUE INDEX stock_client_product_order ON stock_items(product_id,order_id) WHERE kind='client';
CREATE TABLE product_stock_movements(id INTEGER PRIMARY KEY,item_id TEXT NOT NULL REFERENCES stock_items(id),location_id TEXT NOT NULL REFERENCES stock_locations(id),delta INTEGER NOT NULL,before_qty INTEGER NOT NULL,after_qty INTEGER NOT NULL,kind TEXT NOT NULL,source_id TEXT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE INDEX product_stock_balance ON product_stock_movements(item_id,location_id,id);
CREATE TABLE completed_manufacturing(id TEXT PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),item_id TEXT NOT NULL REFERENCES stock_items(id),location_id TEXT NOT NULL REFERENCES stock_locations(id),quantity INTEGER NOT NULL CHECK(quantity>0),order_id TEXT,snapshot TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE TABLE stock_price_history(id INTEGER PRIMARY KEY,item_id TEXT NOT NULL REFERENCES stock_items(id),before_prices TEXT NOT NULL,after_prices TEXT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE TRIGGER product_stock_no_update BEFORE UPDATE ON product_stock_movements BEGIN SELECT RAISE(ABORT,'Movimento histórico imutável'); END;
CREATE TRIGGER product_stock_no_delete BEFORE DELETE ON product_stock_movements BEGIN SELECT RAISE(ABORT,'Movimento histórico imutável'); END;
CREATE TRIGGER completed_manufacturing_no_update BEFORE UPDATE ON completed_manufacturing BEGIN SELECT RAISE(ABORT,'Fabricação histórica imutável'); END;
CREATE TRIGGER completed_manufacturing_no_delete BEFORE DELETE ON completed_manufacturing BEGIN SELECT RAISE(ABORT,'Fabricação histórica imutável'); END;
CREATE TRIGGER stock_price_no_update BEFORE UPDATE ON stock_price_history BEGIN SELECT RAISE(ABORT,'Preço histórico imutável'); END;
CREATE TRIGGER stock_price_no_delete BEFORE DELETE ON stock_price_history BEGIN SELECT RAISE(ABORT,'Preço histórico imutável'); END;
`;
