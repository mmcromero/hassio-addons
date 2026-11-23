import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {schemaVersions} from '../dist-server/foundation/migrations.js';
const release=JSON.parse(readFileSync(new URL('../artesao-release.json',import.meta.url),'utf8'));
const metadata=JSON.parse(readFileSync(new URL('../pilot-build.json',import.meta.url),'utf8'));
assert.deepEqual(release.schemaVersions,schemaVersions,'Schemas executáveis divergem do manifesto comum.');
assert.deepEqual(metadata.schemaVersions,schemaVersions,'Schemas divergem dos metadados de build.');
assert.equal(metadata.releaseVersion,release.version,'Versões de release divergentes.');
console.log('Release e versões de schema comuns verificadas; nenhuma conexão de banco aberta.');
