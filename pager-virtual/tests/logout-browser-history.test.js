import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const root = new URL('../src/', import.meta.url);
test('manager page blocks BFCache restoration until session is checked', () => {
  const html=readFileSync(new URL('public/admin.html',root),'utf8');
  assert.match(html,/addEventListener\('pageshow'/);
  assert.match(html,/addEventListener\('pagehide'/);
  assert.match(html,/cache:'no-store'/);
  assert.match(html,/sessionGuard\.style\.display='flex'/);
  assert.match(html,/if\(!response\.ok\)\{location\.replace/);
});
test('authenticated pages must not be cached',()=>{
  const server=readFileSync(new URL('server.js',root),'utf8');
  assert.match(server,/\['\/login\.html', '\/setup\.html', '\/admin\.html', '\/kds\.html', '\/impressao\.html'\]/);
  assert.match(server,/Cache-Control', 'no-store, no-cache, must-revalidate, private'/);
});
