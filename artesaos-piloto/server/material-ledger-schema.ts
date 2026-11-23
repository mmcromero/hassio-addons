/** B3: somente adições; nenhum saldo é inferido de referências legadas. */
export const materialLedgerSql=`
CREATE TABLE material_categories(id INTEGER PRIMARY KEY,name TEXT NOT NULL,category_key TEXT NOT NULL UNIQUE);
CREATE TABLE material_profiles(material_id INTEGER PRIMARY KEY REFERENCES materials(id),data TEXT NOT NULL,revision INTEGER NOT NULL);
CREATE TABLE material_purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,purchased_on TEXT NOT NULL,supplier TEXT NOT NULL,notes TEXT NOT NULL,total_cents INTEGER NOT NULL CHECK(total_cents>=0),registered_at TEXT NOT NULL,actor TEXT NOT NULL);
CREATE TABLE material_purchase_lines(id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES material_purchases(id),material_id INTEGER NOT NULL REFERENCES materials(id),quantity_micro INTEGER NOT NULL CHECK(quantity_micro>0),total_cents INTEGER NOT NULL CHECK(total_cents>=0),unit TEXT NOT NULL,unit_cost8 TEXT NOT NULL,snapshot TEXT NOT NULL);
CREATE TABLE material_lots(id TEXT PRIMARY KEY,line_id INTEGER REFERENCES material_purchase_lines(id),material_id INTEGER NOT NULL REFERENCES materials(id),label TEXT NOT NULL,registered_at TEXT NOT NULL,unit_cost8 TEXT,quantity_micro INTEGER NOT NULL CHECK(quantity_micro>0),closed INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE material_consumption_events(id INTEGER PRIMARY KEY,material_id INTEGER NOT NULL REFERENCES materials(id),source_id TEXT NOT NULL,quantity_micro INTEGER NOT NULL CHECK(quantity_micro>0),request_key TEXT NOT NULL UNIQUE,registered_at TEXT NOT NULL,UNIQUE(material_id,source_id));
CREATE TABLE material_movements(id INTEGER PRIMARY KEY,material_id INTEGER NOT NULL REFERENCES materials(id),lot_id TEXT REFERENCES material_lots(id),kind TEXT NOT NULL,delta_micro INTEGER NOT NULL,before_micro INTEGER NOT NULL,after_micro INTEGER NOT NULL,unit_cost8 TEXT,analytical_cents INTEGER,reason TEXT NOT NULL,source_id TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE INDEX material_movements_balance ON material_movements(material_id,lot_id,id);
CREATE INDEX material_lots_material ON material_lots(material_id,line_id);
CREATE TABLE material_cost_reference(material_id INTEGER PRIMARY KEY REFERENCES materials(id),purchase_id INTEGER NOT NULL REFERENCES material_purchases(id),unit TEXT NOT NULL,quantity_micro INTEGER NOT NULL,total_cents INTEGER NOT NULL,unit_cost8 TEXT NOT NULL);
CREATE TABLE financial_obligations(id INTEGER PRIMARY KEY,origin TEXT NOT NULL,origin_id INTEGER NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),due_on TEXT,registered_at TEXT NOT NULL,UNIQUE(origin,origin_id));
CREATE TABLE product_current_costs(product_id INTEGER PRIMARY KEY REFERENCES products(id),data TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TRIGGER material_purchase_no_update BEFORE UPDATE ON material_purchases BEGIN SELECT RAISE(ABORT,'Compra histórica imutável'); END;
CREATE TRIGGER material_purchase_no_delete BEFORE DELETE ON material_purchases BEGIN SELECT RAISE(ABORT,'Compra histórica imutável'); END;
CREATE TRIGGER material_lines_no_update BEFORE UPDATE ON material_purchase_lines BEGIN SELECT RAISE(ABORT,'Compra histórica imutável'); END;
CREATE TRIGGER material_lines_no_delete BEFORE DELETE ON material_purchase_lines BEGIN SELECT RAISE(ABORT,'Compra histórica imutável'); END;
CREATE TRIGGER material_movement_no_update BEFORE UPDATE ON material_movements BEGIN SELECT RAISE(ABORT,'Movimento histórico imutável'); END;
CREATE TRIGGER material_movement_no_delete BEFORE DELETE ON material_movements BEGIN SELECT RAISE(ABORT,'Movimento histórico imutável'); END;
CREATE TRIGGER material_consumption_no_update BEFORE UPDATE ON material_consumption_events BEGIN SELECT RAISE(ABORT,'Consumo histórico imutável'); END;
CREATE TRIGGER material_consumption_no_delete BEFORE DELETE ON material_consumption_events BEGIN SELECT RAISE(ABORT,'Consumo histórico imutável'); END;
`;
