import {cp,mkdir,readFile,writeFile,access,chmod,readdir} from "node:fs/promises";
import {createHash} from "node:crypto";
import {execFileSync} from "node:child_process";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const out=path.join(root,"artifacts","portal-governanca");
const run=(cwd,args)=>execFileSync("git",args,{cwd,encoding:"utf8",stdio:["ignore","pipe","pipe"]}).trim();
// Aceita worktrees modificadas. A proveniência registra o HEAD de referência,
// o estado do worktree e os hashes exatos dos arquivos efetivamente empacotados.
// Não exigir checkout limpo nem commit prévio.
const sourceSha=run(root,["rev-parse","HEAD"]);
const sourceStatus=run(root,["status","--porcelain=v1","--untracked-files=all"]);
const sourceStatusEntries=sourceStatus?sourceStatus.split("\n"):[];
const manifestText=await readFile(path.join(root,"addon/config.yaml"),"utf8");
const version=(manifestText.match(/^version:\s*"([^"]+)"/m)||[])[1];
if(!version)throw new Error("Versão não encontrada em addon/config.yaml.");
const lockBytes=await readFile(path.join(root,"package-lock.json"));
const npmLock=JSON.parse(lockBytes.toString("utf8"));
if(npmLock.lockfileVersion!==3)throw new Error("package-lock.json precisa usar lockfileVersion 3.");
const pkg=JSON.parse(await readFile(path.join(root,"package.json"),"utf8"));
const sortObject=value=>Object.fromEntries(Object.entries(value||{}).sort(([a],[b])=>a.localeCompare(b)));
if(JSON.stringify(sortObject(npmLock.packages[""]?.dependencies))!==JSON.stringify(sortObject(pkg.dependencies)))throw new Error("package-lock.json não corresponde ao package.json.");
const ds=JSON.parse(await readFile(path.join(root,"vendor/design-system/PROVENANCE.json"),"utf8"));
const dsLock=JSON.parse(await readFile(path.join(root,"config/design-system.lock.json"),"utf8"));
if(ds.source_commit!==dsLock.sha||ds.source_repository!=="mmcromero/design-system")throw new Error("Snapshot do Design System diverge do SHA fixado.");
if(!Array.isArray(ds.files)||!ds.files.length)throw new Error("Proveniência do snapshot sem lista de arquivos.");
for(const entry of ds.files){
 const file=path.join(root,"vendor/design-system",entry.path);
 const actual=run(root,["hash-object",file]);
 if(actual!==entry.git_blob_sha)throw new Error("Snapshot do Design System alterado ou divergente: "+entry.path);
}
for(const [name,relative] of [["@mmcromero/ds-tokens","vendor/design-system/packages/tokens/package.json"],["@mmcromero/ds-components","vendor/design-system/packages/components/package.json"]]){
 const p=JSON.parse(await readFile(path.join(root,relative),"utf8"));
 if(p.name!==name||p.version!==dsLock.packages[name])throw new Error("Pacote Design System divergente: "+name+".");
}
try{await access(out);throw new Error("Artefato já existe: "+out+". Inspecione/mova o artefato anterior antes de gerar outro.");}
catch(error){if(error.code!=="ENOENT")throw error;}
await mkdir(path.dirname(out),{recursive:true});
await mkdir(out,{recursive:false});
for(const file of ["package.json","package-lock.json","index.html","tsconfig.json","vite.config.ts"])await cp(path.join(root,file),path.join(out,file));
await cp(path.join(root,"addon/Dockerfile"),path.join(out,"Dockerfile"));
for(const file of ["config.yaml","run.sh","README.md","CHANGELOG.md","icon.png","logo.png"])await cp(path.join(root,"addon",file),path.join(out,file));
for(const dir of ["server","src","tests","config","public","scripts","vendor/design-system"])await cp(path.join(root,dir),path.join(out,dir),{recursive:true});
await chmod(path.join(out,"run.sh"),0o755);
async function walk(dir,prefix=""){
 const items=await readdir(dir,{withFileTypes:true}),result=[];
 for(const item of items){
  const relative=path.posix.join(prefix,item.name),absolute=path.join(dir,item.name);
  if(item.isDirectory())result.push(...await walk(absolute,relative));
  else if(item.isFile()){
   const bytes=await readFile(absolute);
   if(/\.(?:html|js|css|json)$/i.test(item.name)){
    const text=bytes.toString("utf8");
    if(/(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})/.test(text))throw new Error("Possível credencial encontrada no pacote: "+relative);
   }
   result.push({path:relative,sha256:createHash("sha256").update(bytes).digest("hex")});
  }
 }
 return result.sort((a,b)=>a.path.localeCompare(b.path));
}
const files=await walk(out);
const packageManifestSha256=createHash("sha256").update(JSON.stringify(files)).digest("hex");
const sourceWorktreeFingerprint=createHash("sha256").update([
 sourceSha,
 sourceStatusEntries.join("\n"),
 packageManifestSha256
].join("\n")).digest("hex");
const provenance={
 product:"Portal de Governança",addon_version:version,
 source_repository:"mmcromero/portal-governanca",source_commit:sourceSha,
 source_worktree:{
  state:sourceStatusEntries.length?"modified":"clean",
  status_entries:sourceStatusEntries,
  fingerprint_sha256:sourceWorktreeFingerprint
 },
 design_system_repository:ds.source_repository,design_system_commit:ds.source_commit,
 design_system_packages:dsLock.packages,design_system_snapshot:"vendor/design-system",
 npm_lockfile_version:npmLock.lockfileVersion,npm_lockfile_sha256:createHash("sha256").update(lockBytes).digest("hex"),
 package_manifest_sha256:packageManifestSha256,
 build_strategy:"Supervisor Docker multi-stage build; npm ci + npm test + npm run build on target architecture",
 files,generated_by:"npm run package:addon"
};
await writeFile(path.join(out,"BUILD-PROVENANCE.json"),JSON.stringify(provenance,null,2)+"\n",{flag:"wx"});
process.stdout.write("Pacote autossuficiente preparado em "+path.relative(root,out)+"\n");
process.stdout.write("Portal: "+sourceSha+"\nDesign System: "+ds.source_commit+"\nVersão add-on: "+version+"\n");
