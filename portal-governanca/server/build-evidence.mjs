import {readFile,writeFile} from "node:fs/promises";
import path from "node:path";
import {pathToFileURL} from "node:url";

const SHA_RE=/^[a-f0-9]{40}$/i;

export function createBuildEvidence({testResults,provenance,architecture,nodeVersion,builtAt=new Date().toISOString()}){
 if(!provenance||typeof provenance!=="object")throw new Error("Proveniência do pacote ausente.");
 if(provenance.source_repository!=="mmcromero/portal-governanca"||!SHA_RE.test(provenance.source_commit||""))throw new Error("Origem ou SHA do Portal inválido.");
 if(provenance.design_system_repository!=="mmcromero/design-system"||!SHA_RE.test(provenance.design_system_commit||""))throw new Error("Proveniência do Design System inválida.");
 if(!/^0\.1\.0-dev\.\d+$/.test(provenance.addon_version||""))throw new Error("Versão do add-on inválida.");
 if(!/^[a-f0-9]{64}$/i.test(provenance.npm_lockfile_sha256||""))throw new Error("Digest do lockfile inválido.");
 if(architecture!=="arm64")throw new Error("O build de homologação exige arquitetura ARM64; recebido: "+String(architecture)+".");
 if(!testResults||testResults.success!==true)throw new Error("A suíte Vitest não terminou com sucesso.");
 const total=Number(testResults.numTotalTests),passed=Number(testResults.numPassedTests),failed=Number(testResults.numFailedTests),pending=Number(testResults.numPendingTests||0),todo=Number(testResults.numTodoTests||0);
 const totalSuites=Number(testResults.numTotalTestSuites),passedSuites=Number(testResults.numPassedTestSuites),failedSuites=Number(testResults.numFailedTestSuites);
 if(!Number.isSafeInteger(total)||total<1||!Number.isSafeInteger(passed)||passed<0||!Number.isSafeInteger(failed)||failed!==0||passed+pending+todo!==total)throw new Error("Resumo de testes incompleto ou com falhas.");
 if(!Number.isSafeInteger(totalSuites)||totalSuites<1||!Number.isSafeInteger(passedSuites)||!Number.isSafeInteger(failedSuites)||failedSuites!==0)throw new Error("Resumo de suítes inválido.");
 if(typeof nodeVersion!=="string"||!/^v\d+\.\d+\.\d+/.test(nodeVersion))throw new Error("Versão do Node inválida.");
 if(!Number.isFinite(Date.parse(builtAt)))throw new Error("Timestamp do build inválido.");
 return {
  schemaVersion:1,
  kind:"supervisor-addon-build",
  status:"PASS",
  builtAt:new Date(builtAt).toISOString(),
  source:{repository:provenance.source_repository,commit:provenance.source_commit},
  addon:{version:provenance.addon_version,architecture:"aarch64",nodeVersion},
  designSystem:{repository:provenance.design_system_repository,commit:provenance.design_system_commit},
  lockfile:{version:3,sha256:provenance.npm_lockfile_sha256},
  tests:{runner:"Vitest",status:"PASS",total,passed,failed,pending,todo,totalSuites,passedSuites,failedSuites,durationMs:Number.isFinite(testResults.duration)?Math.max(0,Math.round(testResults.duration)):null},
  build:{designSystem:"PASS",typescript:"PASS",vite:"PASS",strategy:"Supervisor ARM64 multi-stage Docker build"}
 };
}

async function main(){
 const root=process.cwd();
 const [testText,provenanceText]=await Promise.all([
  readFile(path.join(root,"vitest-results.json"),"utf8"),
  readFile(path.join(root,"BUILD-PROVENANCE.json"),"utf8")
 ]);
 const evidence=createBuildEvidence({testResults:JSON.parse(testText),provenance:JSON.parse(provenanceText),architecture:process.arch,nodeVersion:process.version});
 await writeFile(path.join(root,"dist","build-evidence.json"),JSON.stringify(evidence,null,2)+"\n",{flag:"w"});
 process.stdout.write("Build evidence: PASS · "+evidence.tests.passed+"/"+evidence.tests.total+" testes · "+evidence.source.commit+"\n");
}

if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)await main();
