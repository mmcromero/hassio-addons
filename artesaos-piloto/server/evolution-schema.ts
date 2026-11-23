export const engagementSql=`
ALTER TABLE clients ADD COLUMN commercial_type TEXT NOT NULL DEFAULT 'undefined' CHECK(commercial_type IN ('wholesale','retail','undefined'));
ALTER TABLE clients ADD COLUMN registration_origin TEXT NOT NULL DEFAULT 'undefined' CHECK(registration_origin IN ('quote','sale','direct','undefined'));
ALTER TABLE clients ADD COLUMN capture_session_id TEXT REFERENCES sales_sessions(id);
ALTER TABLE clients ADD COLUMN created_at TEXT;
CREATE INDEX clients_capture_session ON clients(capture_session_id);
CREATE TRIGGER clients_origin_immutable BEFORE UPDATE OF registration_origin,capture_session_id,created_at ON clients BEGIN SELECT RAISE(ABORT,'Origem original imutável'); END;
CREATE TABLE visitor_events(id INTEGER PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sales_sessions(id),request_key TEXT NOT NULL,delta INTEGER NOT NULL CHECK(delta IN (-1,1)),total_after INTEGER NOT NULL CHECK(total_after>=0),actor TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(session_id,request_key));
CREATE INDEX visitor_session ON visitor_events(session_id,id);
CREATE TABLE visitor_preferences(session_id TEXT NOT NULL REFERENCES sales_sessions(id),actor TEXT NOT NULL,expanded INTEGER NOT NULL CHECK(expanded IN (0,1)),PRIMARY KEY(session_id,actor));
CREATE TRIGGER visitor_no_update BEFORE UPDATE ON visitor_events BEGIN SELECT RAISE(ABORT,'Evento imutável'); END;
CREATE TRIGGER visitor_no_delete BEFORE DELETE ON visitor_events BEGIN SELECT RAISE(ABORT,'Evento imutável'); END;
`;
export const resourceSql=`
CREATE TABLE resource_versions(id TEXT PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('terms','privacy','cookies','manual')),version TEXT NOT NULL,content TEXT NOT NULL,payload BLOB,hash TEXT NOT NULL,created_at TEXT NOT NULL,author TEXT NOT NULL,published_at TEXT,published_order INTEGER UNIQUE,requires_acceptance INTEGER NOT NULL DEFAULT 1,UNIQUE(kind,version));
CREATE TABLE resource_active(kind TEXT PRIMARY KEY,resource_id TEXT NOT NULL REFERENCES resource_versions(id));
CREATE TABLE resource_events(id INTEGER PRIMARY KEY,account TEXT NOT NULL,tenant TEXT NOT NULL,document_id TEXT NOT NULL REFERENCES resource_versions(id),action TEXT NOT NULL CHECK(action IN ('accept','acknowledge','refuse','preference')),created_at TEXT NOT NULL,session_context TEXT NOT NULL,manual_id TEXT REFERENCES resource_versions(id));
CREATE INDEX resource_events_account ON resource_events(account,document_id,id);
CREATE TABLE contribution_config(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL,pix_key TEXT NOT NULL,beneficiary TEXT NOT NULL,message TEXT NOT NULL);
INSERT INTO contribution_config VALUES(1,0,'','','');
CREATE TRIGGER resource_published_immutable BEFORE UPDATE ON resource_versions WHEN OLD.published_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'Versão publicada imutável'); END;
CREATE TRIGGER resource_no_delete BEFORE DELETE ON resource_versions BEGIN SELECT RAISE(ABORT,'Versão preservada'); END;
CREATE TRIGGER resource_events_no_update BEFORE UPDATE ON resource_events BEGIN SELECT RAISE(ABORT,'Auditoria imutável'); END;
CREATE TRIGGER resource_events_no_delete BEFORE DELETE ON resource_events BEGIN SELECT RAISE(ABORT,'Auditoria imutável'); END;
`;
