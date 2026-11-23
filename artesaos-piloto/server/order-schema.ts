export const orderSql=`
CREATE TABLE orders(id TEXT PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),client_snapshot TEXT NOT NULL,quote_id INTEGER UNIQUE REFERENCES quotes(id),quote_snapshot TEXT,status TEXT NOT NULL CHECK(status IN ('open','production','ready','delivered','cancelled')),total_cents INTEGER NOT NULL CHECK(total_cents>=0),extra_cents INTEGER NOT NULL CHECK(extra_cents>=0),due_on TEXT,notes TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE order_lines(id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES orders(id),product_id INTEGER REFERENCES products(id),quantity INTEGER NOT NULL CHECK(quantity>0),unit_price INTEGER NOT NULL CHECK(unit_price>=0),snapshot TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE INDEX order_lines_order ON order_lines(order_id,active);
CREATE TABLE stock_reservations(order_id TEXT NOT NULL REFERENCES orders(id),line_id TEXT PRIMARY KEY REFERENCES order_lines(id),item_id TEXT NOT NULL REFERENCES stock_items(id),quantity INTEGER NOT NULL CHECK(quantity>0));
CREATE TABLE order_events(id INTEGER PRIMARY KEY,order_id TEXT NOT NULL REFERENCES orders(id),kind TEXT NOT NULL,snapshot TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE TRIGGER order_events_no_update BEFORE UPDATE ON order_events BEGIN SELECT RAISE(ABORT,'Histórico de pedido imutável'); END;
CREATE TRIGGER order_events_no_delete BEFORE DELETE ON order_events BEGIN SELECT RAISE(ABORT,'Histórico de pedido imutável'); END;
`;
