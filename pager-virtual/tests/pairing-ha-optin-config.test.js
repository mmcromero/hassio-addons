import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { configureRuntime } from '../src/runtime-config.js';

const valid = {pair_v1_enabled:true, public_url:'https://pager.test/avisaqui',
  pair_v1_mount_prefix:'/', pair_v1_approval_ms:'300000',
  pair_v1_challenge_ms:'60000', pair_v1_recovery_ms:'3600000'};
function fixture(options, run) {
  const dir=mkdtempSync(join(tmpdir(),'avisaqui-ha-config-'));
  try { writeFileSync(join(dir,'options.json'),JSON.stringify(options)); return run({DATA_PATH:dir},dir); }
  finally { rmSync(dir,{recursive:true,force:true}); }
}
test('HA padrão OFF e entrypoints independem de bashio',()=>{
  const config=readFileSync(new URL('../config.yaml',import.meta.url),'utf8');
  const runner=readFileSync(new URL('../run.sh',import.meta.url),'utf8');
  assert.match(config,/pair_v1_enabled: false/);
  assert.match(config,/pair_v1_mount_prefix: list\(\/\|\/avisaqui\)/);
  assert.match(runner,/exec node src\/server.js/);
  assert.doesNotMatch(runner,/bashio::|with-contenv/);
  fixture({pair_v1_enabled:false},env=>{configureRuntime(env);assert.equal(env.AVISAQUI_PAIR_V1_ENABLED,'false');});
});
test('options.json habilita somente com política completa e normaliza prefixo removido',()=>{
  for(const prefix of ['/','/avisaqui']) fixture({...valid,pair_v1_mount_prefix:prefix},env=>{
    configureRuntime(env);
    assert.equal(env.AVISAQUI_PAIR_V1_ENABLED,'true');
    assert.equal(env.AVISAQUI_PAIR_V1_PUBLIC_ORIGIN,valid.public_url);
    assert.equal(env.AVISAQUI_PAIR_V1_MOUNT_PREFIX,prefix==='/'?'':prefix);
    assert.equal(env.AVISAQUI_PAIR_V1_RECOVERY_MS,'3600000');
  });
});
test('ambiente explícito OFF prevalece sobre opções ON, sem importar banco',()=>{
  fixture(valid,(env,dir)=>{
    env.AVISAQUI_PAIR_V1_ENABLED='false'; configureRuntime(env);
    assert.equal(env.AVISAQUI_PAIR_V1_ENABLED,'false');
    assert.equal(existsSync(join(dir,'pager_virtual.db')),false);
  });
});
test('configuração incompleta/insegura falha fechada',()=>{
  for(const changes of [{public_url:'http://pager.test/avisaqui'}, {public_url:'https://pager.test/'},
      {pair_v1_enabled:'yes'}, {pair_v1_mount_prefix:'/outro'}, {pair_v1_approval_ms:''},
      {pair_v1_challenge_ms:'0'}, {pair_v1_recovery_ms:'9007199254740992'}])
    fixture({...valid,...changes},env=>assert.throws(()=>configureRuntime(env)));
});
test('entrypoint REAL falha antes de abrir SQLite quando opt-in incompleto',()=>{
  fixture({...valid,pair_v1_approval_ms:''},(env,dir)=>{
    const isolated={...process.env,...env};
    for(const k of Object.keys(isolated)) if(k==='PUBLIC_URL'||k.startsWith('AVISAQUI_PAIR_V1_')) delete isolated[k];
    const result=spawnSync(process.execPath,['src/server.js'],{env:isolated,encoding:'utf8',timeout:10000});
    assert.notEqual(result.status,0);
    assert.match(result.stderr,/Política temporal pair-v1 inválida/);
    assert.equal(existsSync(join(dir,'pager_virtual.db')),false);
  });
});
