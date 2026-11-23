export const saleSql=`
CREATE TABLE sales(id TEXT PRIMARY KEY,number INTEGER NOT NULL UNIQUE,client_id INTEGER REFERENCES clients(id),session_id TEXT,total_cents INTEGER NOT NULL CHECK(total_cents>=0),snapshot TEXT NOT NULL,title_id TEXT NOT NULL UNIQUE REFERENCES finance_titles(id),actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE TABLE sale_coupons(id TEXT PRIMARY KEY,code TEXT NOT NULL UNIQUE,kind TEXT NOT NULL CHECK(kind IN ('percent','fixed')),value INTEGER NOT NULL CHECK(value>=0),starts_on TEXT,ends_on TEXT,max_uses INTEGER,active INTEGER NOT NULL,allow_manual INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE sale_coupon_uses(sale_id TEXT PRIMARY KEY REFERENCES sales(id),coupon_id TEXT NOT NULL REFERENCES sale_coupons(id),discount_cents INTEGER NOT NULL CHECK(discount_cents>=0));
CREATE TABLE attention_events(id TEXT PRIMARY KEY,occurrence_key TEXT NOT NULL UNIQUE,kind TEXT NOT NULL,source_kind TEXT NOT NULL,source_id TEXT NOT NULL,item_ref TEXT,location_id TEXT,quantity INTEGER,value_cents INTEGER,details TEXT NOT NULL,action_href TEXT NOT NULL,priority TEXT NOT NULL CHECK(priority IN ('normal','high')),state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','resolved')),responsible TEXT NOT NULL,created_at TEXT NOT NULL,resolved_at TEXT);
CREATE INDEX attention_state ON attention_events(state,kind,created_at);
CREATE TABLE attention_history(id INTEGER PRIMARY KEY,attention_id TEXT NOT NULL REFERENCES attention_events(id),action TEXT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE TRIGGER sales_no_update BEFORE UPDATE ON sales BEGIN SELECT RAISE(ABORT,'Venda confirmada imutável'); END;
CREATE TRIGGER sales_no_delete BEFORE DELETE ON sales BEGIN SELECT RAISE(ABORT,'Venda confirmada imutável'); END;
CREATE TRIGGER coupon_uses_no_update BEFORE UPDATE ON sale_coupon_uses BEGIN SELECT RAISE(ABORT,'Uso de cupom imutável'); END;
CREATE TRIGGER coupon_uses_no_delete BEFORE DELETE ON sale_coupon_uses BEGIN SELECT RAISE(ABORT,'Uso de cupom imutável'); END;
CREATE TRIGGER attention_history_no_update BEFORE UPDATE ON attention_history BEGIN SELECT RAISE(ABORT,'Tratamento de pendência imutável'); END;
CREATE TRIGGER attention_history_no_delete BEFORE DELETE ON attention_history BEGIN SELECT RAISE(ABORT,'Tratamento de pendência imutável'); END;
`;
