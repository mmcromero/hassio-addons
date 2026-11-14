self.addEventListener('push', event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch {}
  event.waitUntil(self.registration.showNotification(data.title || 'Bipou', {
    body: data.body || 'Seu pedido foi atualizado.',
    tag: data.tag || 'bipou-pedido',
    icon: '/icon.svg',
    badge: '/icon.svg',
    data: { url: typeof data.url === 'string' && data.url.startsWith('/cliente.html?') ?
      data.url : '/cliente.html' }
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const path = event.notification.data?.url || '/cliente.html';
  const target = new URL(path, self.location.origin).href;
  event.waitUntil((async () => {
    const pages = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const page of pages) {
      if (page.url === target) return page.focus();
    }
    return clients.openWindow(target);
  })());
});
