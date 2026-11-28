import assert from 'node:assert/strict';
import {test} from 'node:test';
import {preserveContextParams} from '../src/navigation';

test('preserva sessão e contexto ao trocar de módulo',()=>{
 const current=new URL('https://example.test/artesaos-piloto/?view=produtos&session=abc&tenant=demo');
 const next=new URL('https://example.test/artesaos-piloto/?view=clientes');
 preserveContextParams(next,current);
 assert.equal(next.searchParams.get('view'),'clientes');
 assert.equal(next.searchParams.get('session'),'abc');
 assert.equal(next.searchParams.get('tenant'),'demo');
});

test('não sobrescreve parâmetros explicitamente definidos pela rota de destino',()=>{
 const current=new URL('https://example.test/app/?view=produtos&session=antiga&filter=abertos');
 const next=new URL('https://example.test/app/?view=pedidos&session=nova');
 preserveContextParams(next,current);
 assert.equal(next.searchParams.get('session'),'nova');
 assert.equal(next.searchParams.get('filter'),'abertos');
});

test('não transporta parâmetros de navegação local da tela anterior',()=>{
 const current=new URL('https://example.test/app/?view=configuracoes&settings=frete&area=orcamentos&session=abc');
 const next=new URL('https://example.test/app/?view=clientes');
 preserveContextParams(next,current);
 assert.equal(next.searchParams.has('settings'),false);
 assert.equal(next.searchParams.has('area'),false);
 assert.equal(next.searchParams.get('session'),'abc');
});
