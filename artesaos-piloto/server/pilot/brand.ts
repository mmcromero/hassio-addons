export const communityCss=`*{box-sizing:border-box}.pilot-admin{max-width:1080px;margin:32px auto;padding:24px}.pilot-table{overflow:auto}table{border-collapse:collapse;width:100%}th,td{padding:12px;text-align:left;border-bottom:1px solid #b8c7be;overflow-wrap:anywhere}.pilot-auth section{margin-top:32px;border-top:1px solid #b8c7be;padding-top:16px}.pilot-auth .pilot-consent{display:flex;align-items:flex-start;gap:10px;font-size:14px}.pilot-auth .pilot-consent input{width:20px;height:20px;flex-shrink:0;margin:0}#interest-privacy{font-size:14px;line-height:1.5}#pilot-account{min-height:96px}.pilot-session-active{padding-top:112px}.pilot-account-title img{max-width:100%;height:72px;width:auto;object-fit:contain;border-radius:6px;background:#f7f6f1}#root .app-version{display:none}.pilot-auth [data-pilot-brand]{text-align:center}.pilot-auth [data-pilot-brand] img{height:120px;width:auto;max-width:100%;object-fit:contain}.pilot-admin button{padding:10px 14px;font:inherit}#admin-pagination:not([hidden]){display:flex;gap:16px;align-items:center;margin-top:20px}#pilot-account button{max-width:100%;overflow-wrap:anywhere}@media(max-width:480px){.pilot-table table,.pilot-table tbody,.pilot-table tr,.pilot-table td{display:block}.pilot-table thead{display:none}.pilot-table tr{border:1px solid #b8c7be;border-radius:8px;margin:12px 0;padding:8px}.pilot-table td{border:0;padding:8px}.pilot-table td::before{content:attr(data-label);display:block;font-size:12px;font-weight:700;margin-bottom:4px}.pilot-admin{padding:16px 12px}.pilot-admin h1{font-size:26px}#pilot-account{padding:10px 12px}.pilot-account-title{font-size:15px}#pilot-account button{font-size:13px;padding:8px}}#pilot-account.pilot-account-user-layout{grid-template-columns:minmax(0,auto) minmax(0,1fr) auto;column-gap:16px;padding-inline:max(20px,calc((100% - 860px)/2 + 20px))}#pilot-account.pilot-account-user-layout .pilot-account-user{text-align:right}`;
export const identityCss=`
:root{--mata:#1E4D3B;--areia:#CBB493;--linho:#F5F5EF;--broto:#4F8A5B;--terracota:#B5653A;--carvao:#1F2A25}
:root body{background:var(--linho);color:var(--carvao);font:16px/1.5 Arial,Helvetica,sans-serif}
:root h1,:root h2,:root h3{font-family:Georgia,"Times New Roman",serif;color:var(--mata);line-height:1.3}
:root a{color:var(--mata)}
:root button,:root .pilot-auth button{background:var(--mata);color:var(--linho);font-family:Arial,Helvetica,sans-serif}
:root input,:root select,:root textarea{font:inherit;color:var(--carvao);accent-color:var(--mata)}
:root :focus-visible{outline:3px solid var(--terracota);outline-offset:3px}
:root section,:root .wf-card{border-color:var(--areia)}
:root #pilot-account{background:var(--mata);color:var(--linho)}
:root #pilot-account button{background:var(--linho);color:var(--mata);border-color:var(--areia)}
:root .pilot-account-title{display:flex;align-items:center;padding:10px 14px}
:root .pilot-account-title img{display:block;width:232px;height:auto;max-width:100%;border-radius:0;background:transparent}
:root .pilot-account-title img[hidden]{display:none}
:root .pilot-session-active{padding-top:132px}
:root .pilot-auth [data-pilot-brand]{margin:0 auto 24px;padding:20px;max-width:240px}
:root .pilot-auth [data-pilot-brand] img{display:block;width:180px;min-width:120px;height:auto;max-width:100%;margin:auto}
:root .pilot-auth [data-pilot-brand] img[hidden]{display:none}
:root #pilot-build-info{background:var(--linho);color:var(--carvao);border-color:var(--areia)}
:root .wf-shell{font-family:Arial,Helvetica,sans-serif;color:var(--carvao);background:var(--linho)}
:root .wf-shell h1,:root .wf-shell h2,:root .wf-shell h3{font-family:Georgia,"Times New Roman",serif}
:root .wf-banner{background:var(--mata)}
:root .wf-shell .wf-secondary,:root .products-screen .more-prices{color:var(--mata);border-color:var(--mata);background:var(--linho)}
:root .quote-modal-body{background:var(--linho)}
@media(max-width:480px){:root .pilot-account-title{padding:8px}
:root .pilot-account-title img{width:120px;min-width:120px}
:root .pilot-session-active{padding-top:132px}}
:root .pilot-auth .pilot-introduction{padding:20px 0}
:root .pilot-kicker{font-weight:700;color:var(--mata)}
:root .pilot-login-shortcut{display:inline-block;padding:12px 0;font-weight:700;text-underline-offset:4px}
:root .pilot-auth section{background:white;border:1px solid var(--areia);border-radius:12px;padding:24px;margin:24px 0 40px}
:root .pilot-auth .pilot-login-section{border-top:5px solid var(--mata);scroll-margin-top:24px}
:root .pilot-auth section h2{margin-top:0}
/* The pilot shell owns the green account row and the separate full-width navigation row. */
:root #pilot-shell{display:block;position:fixed;inset:0 0 auto;z-index:3;box-shadow:0 2px 8px #10291e25}
:root #pilot-shell #pilot-account{width:100%;position:static;min-height:88px;box-shadow:none;grid-template-columns:auto minmax(0,1fr) auto;gap:16px;padding:8px max(20px,calc((100% - 1200px)/2))}
:root #pilot-shell .pilot-account-title{padding:8px 12px}
:root #pilot-shell .pilot-account-title img{width:180px;height:auto}
:root #pilot-shell .pilot-account-user{text-align:right}
:root #pilot-navigation{background:var(--linho);color:var(--mata);border-bottom:1px solid var(--areia);max-height:calc(100dvh - 120px);overflow:auto}
:root .pilot-menu{max-width:1200px;margin:auto}
:root #pilot-navigation nav{display:flex;align-items:center;gap:12px;padding:0 20px;flex-wrap:nowrap}
:root #pilot-navigation a{display:flex;align-items:center;gap:10px;padding:16px 18px;color:var(--mata);text-decoration:none;white-space:nowrap;border-bottom:3px solid transparent;min-height:52px}
:root #pilot-navigation a[aria-current=page]{border-color:var(--mata);font-weight:700;background:#1e4d3b08}
:root .pilot-menu-toggle{display:none}
:root .pilot-icon{width:22px;height:22px;flex:none;vertical-align:middle;margin-right:8px}
:root #pilot-navigation .pilot-icon{margin:0}
:root .pilot-session-active #root{padding-top:0}
:root .pilot-session-active #root>main{max-width:1200px;padding:24px 20px 64px}
:root .pilot-session-active #root>main>h1{margin-top:0}
:root .pilot-settings section{background:white}
:root .pilot-settings h2{margin-top:0}
:root .pilot-settings .settings-content section{padding:20px;margin-top:16px;box-shadow:none}
:root .pilot-general details>summary{cursor:pointer;font-weight:700;padding:12px 0;color:var(--mata)}
:root .pilot-settings [role=tablist]{display:flex;border-bottom:1px solid var(--areia);gap:8px;overflow-x:auto}
:root .pilot-settings [role=tab]{background:transparent;color:var(--carvao);border-radius:0;border-bottom:3px solid transparent;margin:0;padding:14px 18px;white-space:nowrap}
:root .pilot-settings [role=tab][aria-selected=true]{border-color:var(--mata);color:var(--mata);font-weight:700}
:root .pilot-settings [role=tabpanel]{padding-top:24px}
:root .pilot-settings [hidden]{display:none}
:root .pilot-settings fieldset{min-width:0}
:root .pilot-settings .setting-field{max-width:100%}
:root .company-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
:root .company-settings fieldset{border:0;padding:0}
:root .company-settings h3{margin-top:0}
:root .pilot-session-active main>header:has(>.brand){display:none}
@media(max-width:700px){
 :root #pilot-shell #pilot-account{padding:8px 12px;gap:8px;min-height:84px}
 :root #pilot-shell .pilot-account-title{padding:8px}
 :root #pilot-shell .pilot-account-title img{width:144px;min-width:120px}
 :root #pilot-shell .pilot-account-user{font-size:12px}
 :root #pilot-navigation .pilot-menu-toggle{display:flex;align-items:center;gap:12px;background:transparent;color:var(--mata);padding:14px 20px;margin:0;border-radius:0;width:100%;text-align:left}
 :root #pilot-navigation nav{display:none;flex-direction:column;align-items:stretch;gap:0;padding:0}
 :root #pilot-navigation .is-open nav{display:flex}
 :root #pilot-navigation a{border-bottom:0;border-left:3px solid transparent;padding:14px 20px}
 :root #pilot-navigation a[aria-current=page]{border-left-color:var(--mata);background:#1e4d3b12}
 :root .pilot-settings .settings-content section{padding:16px 12px}
 :root .pilot-settings [role=tab]{padding:12px 10px}
 :root .company-fields{grid-template-columns:1fr}
 :root .pilot-auth section{padding:20px}
}
@media(max-width:480px){:root #pilot-shell .pilot-account-user{display:none}}

:root #pilot-build-info .pilot-support-link{display:none;pointer-events:auto;font-weight:400;text-underline-offset:3px}
:root .pilot-session-active #pilot-build-info .pilot-support-link{display:inline-flex}
:root body.pilot-first-access-detail{padding-top:0!important;padding-bottom:0}
:root .pilot-first-access-detail #pilot-build-info{display:none}
:root .pilot-first-access-back{max-width:860px;margin:24px auto;padding:0 24px}
:root .support-hub input,:root .support-hub select,:root .support-hub textarea,:root .support-admin input,:root .support-admin select,:root .support-admin textarea{display:block;width:100%;padding:10px;margin-top:6px;border:1px solid #789483;border-radius:8px;background:white;color:var(--carvao);font:inherit}
:root .support-filters{display:flex;align-items:end;gap:16px;flex-wrap:wrap;margin-top:20px}
:root .support-filters label{flex:1;min-width:160px}
:root .support-filters button{margin:0}
:root .support-list article,:root #support-list article{padding:16px 0;border-bottom:1px solid var(--areia);overflow-wrap:anywhere}
:root .support-list article button,:root #support-list article button{background:transparent;color:var(--mata);font-weight:700;text-align:left;padding:8px 0;text-decoration:underline}
:root .support-list article p,:root #support-list article p{margin:6px 0}
:root .support-badge{display:inline-block;border:1px solid var(--areia);border-radius:16px;padding:2px 10px}
:root .support-events{list-style:none;padding:0;margin:24px 0}
:root .support-events li{border:1px solid var(--areia);border-radius:10px;padding:16px;margin:12px 0;background:white;overflow-wrap:anywhere}
:root .support-events small{display:block;margin-top:4px}
:root .support-events p{white-space:pre-wrap;overflow-wrap:anywhere}
:root .support-compose{position:fixed;inset:0;width:min(650px,calc(100vw - 24px));max-height:90dvh;overflow:auto;border:1px solid var(--areia);border-radius:12px;padding:24px;color:var(--carvao);background:var(--linho)}
:root .support-compose::backdrop{background:#10291eaa}
:root .support-compose label{display:block;margin-top:16px;font-weight:600}
:root .support-compose fieldset,:root .support-conversation fieldset{border:0;padding:0;min-width:0}
:root .support-secondary{background:white;color:var(--mata);border:1px solid var(--mata);margin-left:8px}
:root .pilot-admin-nav{display:flex;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--areia);padding-bottom:16px}
:root .pilot-admin-nav a[aria-current=page]{font-weight:700}
:root #user-details dt,:root .invitations-admin dt{font-weight:700}
:root #user-details dd,:root .invitations-admin dd{margin:0 0 16px;overflow-wrap:anywhere}
:root .invitations-admin code{display:block;overflow-wrap:anywhere;margin-bottom:16px}
:root .users-admin label,:root .invitations-admin label{display:block;margin:16px 0}
:root .users-admin input,:root .invitations-admin input,:root .invitations-admin select,:root .invitations-admin textarea{box-sizing:border-box;max-width:100%;width:100%;padding:10px}
:root .invitations-admin button,:root .invitations-admin #invitation-detail a{margin:8px 12px 8px 0}
:root #users-pagination:not([hidden]),:root #invitations-pagination:not([hidden]){display:flex;align-items:center;gap:12px;flex-wrap:wrap}
:root #support-pagination{display:flex;gap:16px;align-items:center;margin-top:20px}
:root #support-pagination[hidden]{display:none}
:root .support-admin #support-detail[hidden]{display:none}
:root .support-admin #support-detail{margin-top:32px;padding:24px;border:1px solid var(--areia);border-radius:12px}
:root .support-admin textarea{min-height:120px}
:root .support-admin button{border:1px solid var(--mata);border-radius:8px;cursor:pointer}
:root .support-admin button:disabled{opacity:.5;cursor:wait}
:root .pilot-session-active{padding-bottom:110px}
@media(max-width:480px){:root .support-compose{padding:20px 16px}:root .support-admin #support-detail{padding:16px}:root .pilot-session-active{padding-bottom:132px}}

`;
export function brandScript(prefix:string,version:string,available:boolean){return `(()=>{window.pilotBrand=parent=>{parent.replaceChildren();const text=document.createElement('span');text.textContent='Artesão Digital';parent.append(text);if(!${available})return;const img=document.createElement('img');img.alt='Artesão Digital';img.hidden=true;img.onload=()=>{text.hidden=true;img.hidden=false;};img.onerror=()=>{img.remove();text.hidden=false;};parent.append(img);img.src=parent.matches('.pilot-account-title,[data-pilot-brand=horizontal]')?${JSON.stringify(prefix+'brand/logo-horizontal.png?v='+version)}:${JSON.stringify(prefix+'brand/logo.png?v='+version)};};addEventListener('DOMContentLoaded',async()=>{try{await window.pilotBrowserReady;}catch{return;}document.querySelectorAll('[data-pilot-brand]').forEach(window.pilotBrand);});})();`;}
