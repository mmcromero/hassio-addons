export const financeSql=`
CREATE TABLE finance_accounts(id TEXT PRIMARY KEY,name TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
INSERT INTO finance_accounts VALUES('general','Caixa Geral',1);
CREATE TABLE finance_methods(id TEXT PRIMARY KEY,name TEXT NOT NULL,fee_bps INTEGER NOT NULL DEFAULT 0 CHECK(fee_bps BETWEEN 0 AND 10000),fixed_fee INTEGER NOT NULL DEFAULT 0 CHECK(fixed_fee>=0),delay_days INTEGER NOT NULL DEFAULT 0 CHECK(delay_days BETWEEN 0 AND 365),revision INTEGER NOT NULL DEFAULT 1);
INSERT INTO finance_methods(id,name) VALUES('pix','Pix'),('cash','Dinheiro'),('debit','Débito'),('credit','Crédito');
CREATE TABLE finance_titles(id TEXT PRIMARY KEY,direction TEXT NOT NULL CHECK(direction IN ('in','out')),origin TEXT NOT NULL,origin_id TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),due_on TEXT,client_id INTEGER REFERENCES clients(id),description TEXT NOT NULL,metadata TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,UNIQUE(origin,origin_id));
CREATE TABLE finance_payments(id TEXT PRIMARY KEY,title_id TEXT NOT NULL REFERENCES finance_titles(id),account_id TEXT NOT NULL REFERENCES finance_accounts(id),method_id TEXT NOT NULL REFERENCES finance_methods(id),amount_cents INTEGER NOT NULL CHECK(amount_cents>0),fee_cents INTEGER NOT NULL CHECK(fee_cents>=0),expected_on TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('scheduled','settled','cancelled')),snapshot TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE finance_entries(id TEXT PRIMARY KEY,title_id TEXT REFERENCES finance_titles(id),account_id TEXT REFERENCES finance_accounts(id),allocation_cents INTEGER NOT NULL,cash_cents INTEGER NOT NULL,fee_cents INTEGER NOT NULL,kind TEXT NOT NULL,source_id TEXT NOT NULL,payment_id TEXT REFERENCES finance_payments(id),snapshot TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL,UNIQUE(kind,source_id));
CREATE TRIGGER finance_payment_details BEFORE UPDATE OF title_id,account_id,method_id,amount_cents,fee_cents,expected_on,snapshot,actor,created_at ON finance_payments BEGIN SELECT RAISE(ABORT,'Dados do pagamento imutáveis'); END;
CREATE INDEX finance_entries_title ON finance_entries(title_id,registered_at);
CREATE TABLE finance_credits(id TEXT PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES clients(id),entry_id TEXT NOT NULL UNIQUE REFERENCES finance_entries(id),amount_cents INTEGER NOT NULL CHECK(amount_cents>0),created_at TEXT NOT NULL);
CREATE TABLE finance_credit_uses(id TEXT PRIMARY KEY,credit_id TEXT NOT NULL REFERENCES finance_credits(id),entry_id TEXT NOT NULL UNIQUE REFERENCES finance_entries(id),amount_cents INTEGER NOT NULL CHECK(amount_cents>0));
CREATE TABLE finance_recurring(id TEXT PRIMARY KEY,description TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),due_day INTEGER NOT NULL CHECK(due_day BETWEEN 1 AND 31),active INTEGER NOT NULL DEFAULT 1,revision INTEGER NOT NULL DEFAULT 1);
CREATE TRIGGER finance_entries_no_update BEFORE UPDATE ON finance_entries BEGIN SELECT RAISE(ABORT,'Histórico financeiro imutável'); END;
CREATE TRIGGER finance_entries_no_delete BEFORE DELETE ON finance_entries BEGIN SELECT RAISE(ABORT,'Histórico financeiro imutável'); END;
CREATE TRIGGER finance_credits_no_update BEFORE UPDATE ON finance_credits BEGIN SELECT RAISE(ABORT,'Crédito histórico imutável'); END;
CREATE TRIGGER finance_credits_no_delete BEFORE DELETE ON finance_credits BEGIN SELECT RAISE(ABORT,'Crédito histórico imutável'); END;
CREATE TRIGGER finance_credit_uses_no_update BEFORE UPDATE ON finance_credit_uses BEGIN SELECT RAISE(ABORT,'Uso de crédito imutável'); END;
CREATE TRIGGER finance_credit_uses_no_delete BEFORE DELETE ON finance_credit_uses BEGIN SELECT RAISE(ABORT,'Uso de crédito imutável'); END;
INSERT INTO finance_titles(id,direction,origin,origin_id,amount_cents,due_on,description,metadata,created_at)
SELECT 'purchase:'||origin_id,'out',origin,CAST(origin_id AS TEXT),amount_cents,due_on,'Compra de materiais '||origin_id,json_object('obligationId',f.id,'purchaseId',f.origin_id,'materialIds',json((SELECT json_group_array(material_id) FROM material_purchase_lines WHERE purchase_id=f.origin_id))),registered_at FROM financial_obligations f;
INSERT INTO finance_titles(id,direction,origin,origin_id,amount_cents,due_on,client_id,description,metadata,created_at)
SELECT 'order:'||id,'in','order',id,CASE WHEN status='cancelled' THEN 0 ELSE total_cents END,due_on,client_id,'Pedido '||id,json_object('orderId',o.id,'productIds',json((SELECT json_group_array(product_id) FROM order_lines WHERE order_id=o.id AND active=1))),created_at FROM orders o;
`;
