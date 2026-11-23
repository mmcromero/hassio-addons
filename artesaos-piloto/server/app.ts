import {registerAttentionCorrections} from './attention-correction.js';
import {registerProductPhotos} from './product-photos.js';
import {registerSessionEngagement} from './session-engagement.js';
import {registerShipping} from './shipping.js';
import {registerAttentionCenter} from './attention-center.js';
import {registerDistribution} from './distribution.js';
import {registerSales} from './sales.js';
import {registerFinance} from './finance.js';
import {registerOrders} from './orders.js';
import {registerProductStock} from './product-stock.js';
import {registerMaterialLedger} from './material-ledger.js';
import {initializeLegacyBase} from './foundation/legacy-schema.js';
import {initializeDatabase} from './foundation/migrations.js';
import {registerCompanyLogo} from './pilot/company-logo.js';
import {registerQuoteDocuments} from './pilot/quote-document.js';
import {registerOnboarding} from './pilot/onboarding.js';
import {registerCompany} from './pilot/company.js';
import {registerLegacyMaterialUpgrade} from './legacy-material-upgrade.js';
import {registerMaterials} from './materials.js';
import {registerProductEditor} from './product-editor.js';
import {registerRecordActions} from './record-actions.js';
import {registerReconciliation} from './reconciliation.js';
import {registerManufacturing} from './manufacturing.js';
import {registerCategories} from './categories.js';
import Fastify from 'fastify';
import { registerQuotes } from './quotes.js';
import { registerSettings } from './settings.js';
import { registerClients } from './clients.js';
import { registerProducts } from './products.js';
import staticFiles from '@fastify/static';
import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { registerHomeAssistantAccess } from './adapters/home-assistant.js';
import type { AppMode } from './config.js';

export async function createApp(options: { dataDir: string; staticDir: string; mode: AppMode; logRequests?:boolean;pilotFeatures?:boolean;actorId?:string }) {
  const { dataDir, staticDir, mode } = options;
  mkdirSync(dataDir, { recursive: true });
  const db = new DatabaseSync(resolve(dataDir, 'validation.sqlite'));
  if(options.pilotFeatures)initializeDatabase(db,'tenant');else initializeLegacyBase(db);

  const app = Fastify({ logger: options.logRequests??true, bodyLimit: 4096, trustProxy: false });
  if (mode === 'home-assistant') registerHomeAssistantAccess(app);
  if(options.pilotFeatures)app.addHook('preValidation',async(req,reply)=>{
    // This header is supplied only by the authenticated gateway.
    const grants=req.headers['x-pilot-modules'];if(typeof grants!=='string'||grants.split(',').includes('fabricacao')||['GET','HEAD','OPTIONS'].includes(req.method))return;
    let path:string;try{path=decodeURIComponent(new URL(req.url,'https://internal.invalid').pathname);}catch{return reply.code(400).send({message:'Endereço inválido.'});}
    if(!path.startsWith('/api/products'))return;
    const body=req.body as any;if(!body)return;
    if(path.endsWith('/reconcile')||(path.endsWith('/import')&&Array.isArray(body.products)&&body.products.some((p:any)=>p&&typeof p==='object'&&Object.hasOwn(p,'manufacturing'))))return reply.code(403).send({code:'MODULE_UNAVAILABLE',message:'A importação técnica requer liberação de Fabricação.'});
    const product=body.product??body;const id=path.match(/^\/api\/products\/(\d+)(?:\/editor)?$/)?.[1];
    const row=id?db.prepare('SELECT data FROM products WHERE id=?').get(id):null;
    const old=row?JSON.parse(String(row.data)).manufacturing:undefined;
    if((Object.hasOwn(product,'manufacturing')&&JSON.stringify(product.manufacturing)!==JSON.stringify(old))||body.applyPrices||(body.applyTiers?.length??0)>0)return reply.code(403).send({code:'MODULE_UNAVAILABLE',message:'Fabricação ainda não liberada. Os dados existentes foram preservados.'});
    if(old&&!Object.hasOwn(product,'manufacturing'))product.manufacturing=old;
  });
  app.addHook('onSend', async (_request, reply, payload) => {
    reply.header('X-Content-Type-Options', 'nosniff');
    reply.header('Cache-Control', 'no-store');
    return payload;
  });
  app.get('/api/health', () => {
    db.prepare('SELECT 1').get();
    return { status: 'ok', database: 'ok', arch: process.arch, node: process.version };
  });
  app.get('/api/note', () => db.prepare('SELECT text, updated_at FROM notes WHERE id = 1').get() ?? { text: '', updated_at: null });
  app.put<{ Body: { text: string } }>('/api/note', {
    schema: { body: { type: 'object', additionalProperties: false, required: ['text'], properties: { text: { type: 'string', maxLength: 500 } } } }
  }, request => {
    const updatedAt = new Date().toISOString();
    db.prepare('INSERT INTO notes (id, text, updated_at) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET text=excluded.text, updated_at=excluded.updated_at').run(request.body.text, updatedAt);
    return { text: request.body.text, updated_at: updatedAt };
  });
  if(options.pilotFeatures)registerCompany(app,db);
  registerMaterials(app, db,options.pilotFeatures??false);
  if(options.pilotFeatures){registerShipping(app,db,options.actorId??'local-development');registerMaterialLedger(app,db,options.actorId??'local-development');registerProductStock(app,db,options.actorId??'local-development');registerOrders(app,db,options.actorId??'local-development');registerFinance(app,db,options.actorId??'local-development');registerSales(app,db,options.actorId??'local-development');registerDistribution(app,db,options.actorId??'local-development');registerAttentionCenter(app,db,options.actorId??'local-development');registerAttentionCorrections(app,db,options.actorId??'local-development');}
  if(options.pilotFeatures)registerProductPhotos(app,db,dataDir);
  registerProducts(app, db,options.pilotFeatures??false);
  registerCategories(app, db);
  registerClients(app, db,options.pilotFeatures??false);
  if(options.pilotFeatures)registerSessionEngagement(app,db,options.actorId??'local-development');
  registerSettings(app, db,options.pilotFeatures??false);
  registerManufacturing(app, db,options.pilotFeatures??false);
  registerQuotes(app, db,options.pilotFeatures??false);
  if(options.pilotFeatures){registerCompanyLogo(app,db);registerQuoteDocuments(app,db);}
  registerReconciliation(app, db,options.pilotFeatures??false);
  registerProductEditor(app, db,options.pilotFeatures??false,options.actorId??'local-development');
  registerRecordActions(app, db,options.pilotFeatures??false);
  registerLegacyMaterialUpgrade(app, db);
  if(options.pilotFeatures)registerOnboarding(app,db);
  await app.register(staticFiles, { root: staticDir });
  app.addHook('onClose', async () => { db.close(); });
  return app;
}
