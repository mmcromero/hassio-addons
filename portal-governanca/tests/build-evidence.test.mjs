import {describe,expect,it} from "vitest";
import {createBuildEvidence} from "../server/build-evidence.mjs";

const provenance={
 source_repository:"mmcromero/portal-governanca",
 source_commit:"a".repeat(40),
 addon_version:"0.1.0-dev.42",
 design_system_repository:"mmcromero/design-system",
 design_system_commit:"b".repeat(40),
 npm_lockfile_sha256:"c".repeat(64)
};
const testResults={
 success:true,numTotalTests:120,numPassedTests:118,numFailedTests:0,numPendingTests:2,numTodoTests:0,
 numTotalTestSuites:20,numPassedTestSuites:20,numFailedTestSuites:0,duration:1234
};
const valid={testResults,provenance,architecture:"arm64",nodeVersion:"v22.15.0",builtAt:"2026-11-27T18:00:00.000Z"};

describe("Supervisor build evidence",()=>{
 it("emits a provenance-bound ARM64 PASS with exact Vitest counts",()=>{
  const result=createBuildEvidence(valid);
  expect(result.status).toBe("PASS");
  expect(result.addon.architecture).toBe("aarch64");
  expect(result.tests).toMatchObject({total:120,passed:118,failed:0,pending:2,totalSuites:20});
  expect(result.source.commit).toBe(provenance.source_commit);
 });
 it("rejects a failed test run",()=>{
  expect(()=>createBuildEvidence({...valid,testResults:{...testResults,success:false,numFailedTests:1}})).toThrow(/não terminou com sucesso/);
 });
 it("rejects a report with failed tests even when success is incorrectly true",()=>{
  expect(()=>createBuildEvidence({...valid,testResults:{...testResults,numFailedTests:1,numPassedTests:117}})).toThrow(/incompleto ou com falhas/);
 });
 it("rejects non-ARM64 builds",()=>{
  expect(()=>createBuildEvidence({...valid,architecture:"x64"})).toThrow(/exige arquitetura ARM64/);
 });
 it("rejects unbound or malformed source provenance",()=>{
  expect(()=>createBuildEvidence({...valid,provenance:{...provenance,source_commit:"unknown"}})).toThrow(/SHA do Portal inválido/);
 });
 it("rejects a report with no executed tests",()=>{
  expect(()=>createBuildEvidence({...valid,testResults:{...testResults,numTotalTests:0,numPassedTests:0,numPendingTests:0}})).toThrow(/incompleto ou com falhas/);
 });
});
