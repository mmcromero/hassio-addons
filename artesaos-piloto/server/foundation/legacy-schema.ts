import type {DatabaseSync} from 'node:sqlite';
import {normalizeStoredMinimums} from '../pilot/minimum-settings.js';
import {applyLegacyMaterialUpgrade} from '../legacy-material-upgrade.js';
export const legacySql={
tenant:`CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS materials(id INTEGER PRIMARY KEY,material_key TEXT NOT NULL UNIQUE,data TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, data TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS product_sources (source_key TEXT PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id));
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY,path TEXT NOT NULL,category_key TEXT NOT NULL UNIQUE,reserved INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, data TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS area_settings (area TEXT PRIMARY KEY, data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY, data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS quote_versions (quote_id INTEGER NOT NULL, revision INTEGER NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(quote_id,revision));
CREATE TABLE IF NOT EXISTS company_profile (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS company_logo(id INTEGER PRIMARY KEY CHECK(id=1), image BLOB, revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS pilot_onboarding(id INTEGER PRIMARY KEY CHECK(id=1), completed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quote_documents(quote_id INTEGER NOT NULL, edition INTEGER NOT NULL, source_revision INTEGER NOT NULL, finalized_at TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(quote_id,edition));
CREATE TABLE IF NOT EXISTS manufacturing_material_upgrade(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS manufacturing_material_backup(product_id INTEGER PRIMARY KEY,data TEXT NOT NULL,updated_at TEXT NOT NULL)`,
control:`CREATE TABLE IF NOT EXISTS legacy_data_jobs(name TEXT PRIMARY KEY,completed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pilot_users(id TEXT PRIMARY KEY,issuer TEXT NOT NULL,subject TEXT NOT NULL,email TEXT NOT NULL,tenant_id TEXT UNIQUE NOT NULL,disabled INTEGER NOT NULL DEFAULT 0,UNIQUE(issuer,subject));
 CREATE TABLE IF NOT EXISTS pilot_invites(hash TEXT PRIMARY KEY,email TEXT NOT NULL,expires_at INTEGER NOT NULL,used_at INTEGER,revoked INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS pilot_flows(hash TEXT PRIMARY KEY,browser_hash TEXT NOT NULL,verifier TEXT NOT NULL,nonce TEXT NOT NULL,invite_hash TEXT NOT NULL,expires_at INTEGER NOT NULL,purpose TEXT NOT NULL DEFAULT 'user');
 CREATE TABLE IF NOT EXISTS pilot_sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES pilot_users(id),csrf_hash TEXT NOT NULL,expires_at INTEGER NOT NULL,last_seen INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS pilot_admin_sessions(hash TEXT PRIMARY KEY,email TEXT NOT NULL,subject TEXT NOT NULL,csrf_hash TEXT NOT NULL,expires_at INTEGER NOT NULL,last_seen INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS pilot_limits(key TEXT PRIMARY KEY,window_start INTEGER NOT NULL,count INTEGER NOT NULL);
 
CREATE TABLE IF NOT EXISTS pilot_invitation_details(hash TEXT PRIMARY KEY REFERENCES pilot_invites(hash),created_at INTEGER NOT NULL,created_by TEXT NOT NULL,request_key TEXT NOT NULL UNIQUE,iv BLOB NOT NULL,tag BLOB NOT NULL,payload BLOB NOT NULL);
  CREATE TABLE IF NOT EXISTS pilot_invitation_deliveries(id TEXT PRIMARY KEY,invite_hash TEXT NOT NULL REFERENCES pilot_invites(hash),request_key TEXT NOT NULL UNIQUE,actor TEXT NOT NULL,started_at INTEGER NOT NULL,finished_at INTEGER,method TEXT NOT NULL,status TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS pilot_invitation_keycheck(id INTEGER PRIMARY KEY CHECK(id=1),iv BLOB NOT NULL,tag BLOB NOT NULL,payload BLOB NOT NULL);
  `,
interest:`CREATE TABLE IF NOT EXISTS interests(id TEXT PRIMARY KEY,created_at INTEGER NOT NULL,email_hash TEXT UNIQUE,phone_hash TEXT UNIQUE,iv BLOB NOT NULL,tag BLOB NOT NULL,payload BLOB NOT NULL);
   CREATE TABLE IF NOT EXISTS metadata(id INTEGER PRIMARY KEY CHECK(id=1),iv BLOB NOT NULL,tag BLOB NOT NULL,payload BLOB NOT NULL);
   CREATE TABLE IF NOT EXISTS form_tokens(hash TEXT PRIMARY KEY,browser_hash TEXT NOT NULL,expires_at INTEGER NOT NULL);`,
support:`CREATE TABLE IF NOT EXISTS support_tickets(id INTEGER PRIMARY KEY AUTOINCREMENT,owner TEXT NOT NULL,email TEXT NOT NULL,kind TEXT NOT NULL,subject TEXT NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,request_key TEXT NOT NULL,UNIQUE(owner,request_key));
   CREATE TABLE IF NOT EXISTS support_events(id INTEGER PRIMARY KEY AUTOINCREMENT,ticket_id INTEGER NOT NULL REFERENCES support_tickets(id),actor TEXT NOT NULL,role TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,request_key TEXT NOT NULL,UNIQUE(ticket_id,actor,request_key));
   CREATE INDEX IF NOT EXISTS support_owner_updated ON support_tickets(owner,updated_at DESC);
   CREATE INDEX IF NOT EXISTS support_status_updated ON support_tickets(status,updated_at DESC);
   CREATE INDEX IF NOT EXISTS support_event_ticket ON support_events(ticket_id,id);`,
legal:`CREATE TABLE IF NOT EXISTS documents(kind TEXT NOT NULL,version TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(kind,version)); CREATE TABLE IF NOT EXISTS acceptances(account TEXT NOT NULL,version TEXT NOT NULL,accepted_at TEXT NOT NULL,PRIMARY KEY(account,version))`
} as const;
const column=(db:DatabaseSync,table:string,name:string,definition:string)=>{if(!db.prepare(`PRAGMA table_info(${table})`).all().some(row=>row.name===name))db.exec(`ALTER TABLE ${table} ADD COLUMN ${name} ${definition}`);};
export function upgradeControl(db:DatabaseSync){
 column(db,'pilot_flows','purpose',"TEXT NOT NULL DEFAULT 'user'");
 column(db,'pilot_invites','binding_mode',"TEXT NOT NULL DEFAULT 'email'");
 column(db,'pilot_invites','accepted_user_id','TEXT');
 const expiry=db.prepare('PRAGMA table_info(pilot_invites)').all().some(row=>row.name==='no_expiry');
 column(db,'pilot_invites','no_expiry','INTEGER NOT NULL DEFAULT 0');
 if(!expiry)db.prepare('UPDATE pilot_invites SET no_expiry=1 WHERE used_at IS NULL AND revoked=0 AND expires_at>?').run(Date.now());
 for(const name of ['phone_hash','previous_hash','replacement_hash'])column(db,'pilot_invitation_details',name,'TEXT');
 db.exec(`CREATE INDEX IF NOT EXISTS pilot_users_email_idx ON pilot_users(email,id);
CREATE INDEX IF NOT EXISTS pilot_invites_contact_idx ON pilot_invites(email,used_at,revoked);
CREATE INDEX IF NOT EXISTS pilot_invitation_phone_idx ON pilot_invitation_details(phone_hash);
CREATE INDEX IF NOT EXISTS pilot_invitation_user_idx ON pilot_invites(accepted_user_id);
CREATE INDEX IF NOT EXISTS pilot_invitation_state_idx ON pilot_invites(used_at,revoked,no_expiry,expires_at);`);
}

export function upgradeTenant(db:DatabaseSync,pilot=true){
 const hadSearch=db.prepare('PRAGMA table_info(quotes)').all().some(row=>row.name==='search_text');
 column(db,'quotes','search_text',"TEXT NOT NULL DEFAULT ''");
 if(!hadSearch){const update=db.prepare('UPDATE quotes SET search_text=? WHERE id=?');for(const row of db.prepare('SELECT id,data FROM quotes').all()){const d=JSON.parse(String(row.data));const text=`${d.title??''} ${d.client?.name??''} ${d.client?.contact??''}`.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase();update.run(text,row.id);}}
 for(const row of db.prepare("SELECT id,data FROM products WHERE json_extract(data,'$.origin')='client'").all()){const d=JSON.parse(String(row.data));db.prepare('UPDATE products SET data=? WHERE id=?').run(JSON.stringify({...d,catalogVisible:pilot?false:(d.catalogVisible??false),publicAllowed:false,category:'Produtos de cliente'}),row.id);}
 const key=(s:string)=>s.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase('pt-BR');
 db.prepare('INSERT OR IGNORE INTO categories(path,category_key,reserved) VALUES(?,?,1)').run('Produtos de cliente',key('Produtos de cliente'));
 for(const row of db.prepare("SELECT data FROM products WHERE json_extract(data,'$.origin')='own'").all()){const path=JSON.parse(String(row.data)).category;if(typeof path!=='string'||!path.trim())continue;let parent='';for(const part of path.split('>').map((s:string)=>s.trim())){const value=parent?parent+' > '+part:part;db.prepare('INSERT OR IGNORE INTO categories(path,category_key) VALUES(?,?)').run(value,key(value));parent=String(db.prepare('SELECT path FROM categories WHERE category_key=?').get(key(value))!.path);}}
 if(pilot)normalizeStoredMinimums(db);
 if(!db.prepare('SELECT id FROM manufacturing_material_upgrade WHERE id=1').get())db.prepare('INSERT INTO manufacturing_material_upgrade VALUES(1,?)').run(JSON.stringify({cutoff:Number(db.prepare('SELECT COALESCE(MAX(id),0) n FROM products').get()!.n),complete:false,changed:0,reason:''}));
 applyLegacyMaterialUpgrade(db);
}

export function initializeLegacyBase(db:DatabaseSync){db.exec(legacySql.tenant);upgradeTenant(db,false);}
