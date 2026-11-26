const pick=(value)=>typeof value==="string"?value:null;
export function normalizeSupervisorApp(payload,requestedSlug){
 const app=payload?.data?.slug?payload.data:payload?.data?.app??payload?.app??payload?.data;
 if(!app||typeof app!=="object"||Array.isArray(app))throw new Error("Resposta de informações do app inválida.");
 const slug=pick(app.slug)||requestedSlug||null;
 const name=pick(app.name);
 if(!slug||!name)return null;
 return {
  slug,name,state:pick(app.state)||"unknown",
  version:pick(app.version),versionLatest:pick(app.version_latest),
  updateAvailable:typeof app.update_available==="boolean"?app.update_available:null,
  boot:pick(app.boot),watchdog:typeof app.watchdog==="boolean"?app.watchdog:null,
  ingressPanel:typeof app.ingress_panel==="boolean"?app.ingress_panel:null,
  protected:typeof app.protected==="boolean"?app.protected:null,
  autoUpdate:typeof app.auto_update==="boolean"?app.auto_update:null
 };
}
