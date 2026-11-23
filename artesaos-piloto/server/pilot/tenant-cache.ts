import type {FastifyInstance} from 'fastify';
export class TenantCapacityError extends Error{}
type Entry={app:Promise<FastifyInstance>;active:number;used:number};
// Limit open application/SQLite instances, not registered accounts.
export class TenantCache{
 private entries=new Map<string,Entry>();private tick=0;private closed=false;
 constructor(private factory:(id:string)=>Promise<FastifyInstance>,private limit=8){if(!Number.isInteger(limit)||limit<1)throw Error('Limite interno inválido.');}
 async use<T>(id:string,fn:(app:FastifyInstance)=>Promise<T>):Promise<T>{
  if(this.closed)throw new TenantCapacityError('O aplicativo está reiniciando. Tente novamente.');
  let entry=this.entries.get(id);
  if(!entry){
   let previous:Entry|undefined;
   if(this.entries.size>=this.limit){const idle=[...this.entries].filter(([,value])=>value.active===0).sort((a,b)=>a[1].used-b[1].used)[0];if(!idle)throw new TenantCapacityError('Aplicativo ocupado. Aguarde e tente novamente.');this.entries.delete(idle[0]);previous=idle[1];}
   const app=Promise.resolve().then(async()=>{if(previous)await(await previous.app).close();return this.factory(id);});
   entry={app,active:0,used:++this.tick};this.entries.set(id,entry);const created=entry;void app.catch(()=>{if(this.entries.get(id)===created)this.entries.delete(id);});
  }
  entry.active++;entry.used=++this.tick;
  try{return await fn(await entry.app);}finally{entry.active--;entry.used=++this.tick;}
 }
 async close(){this.closed=true;const entries=[...this.entries.values()];this.entries.clear();await Promise.all(entries.map(async entry=>{let app:FastifyInstance;try{app=await entry.app;}catch{return;}await app.close();}));}
}
