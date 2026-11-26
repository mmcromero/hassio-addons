const pick=(value)=>typeof value==="string"?value:null;
export function normalizeSupervisorInventory(payload){
 const apps=payload?.data?.apps??payload?.apps??payload?.data?.addons??payload?.addons;
 if(!Array.isArray(apps))throw new Error("Resposta do Supervisor sem lista de apps.");
 return apps.map(app=>({
  slug:pick(app?.slug),
  name:pick(app?.name),
  state:pick(app?.state)||"unknown",
  version:pick(app?.version),
  versionLatest:pick(app?.version_latest),
  updateAvailable:typeof app?.update_available==="boolean"?app.update_available:null,
  boot:pick(app?.boot),
  watchdog:typeof app?.watchdog==="boolean"?app.watchdog:null,
  ingressPanel:typeof app?.ingress_panel==="boolean"?app.ingress_panel:null,
  protected:typeof app?.protected==="boolean"?app.protected:null,
  autoUpdate:typeof app?.auto_update==="boolean"?app.auto_update:null
 })).filter(app=>app.slug&&app.name);
}
