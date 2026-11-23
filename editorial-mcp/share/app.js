const $=s=>document.querySelector(s);let queue=[];
const status=t=>$('#status').textContent=t;
async function db(){return new Promise((ok,no)=>{const r=indexedDB.open('editorial-share',1);r.onupgradeneeded=()=>r.result.createObjectStore('inbox',{keyPath:'id',autoIncrement:true});r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)})}
async function loadQueue(){const d=await db();queue=await new Promise((ok,no)=>{const r=d.transaction('inbox').objectStore('inbox').getAll();r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error)});const cutoff=Date.now()-24*60*60*1000;const stale=queue.filter(x=>!x.created||x.created<cutoff);if(stale.length){const tx=d.transaction('inbox','readwrite');for(const x of stale)tx.objectStore('inbox').delete(x.id);queue=queue.filter(x=>!stale.includes(x))}render()}
function render(){$('#files').innerHTML='';queue.forEach((x,i)=>{const el=document.createElement('div');el.className='file';el.textContent=(i+1)+'. '+(x.file.name||'imagem compartilhada')+' — '+Math.round(x.file.size/1024)+' KB';$('#files').append(el)})}
$('#pick').addEventListener('change',e=>{for(const file of e.target.files)queue.push({file});render()});
async function api(path,body){return fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':$('#key').value},body:JSON.stringify(body)})}
$('#key').addEventListener('change',async()=>{try{const r=await api('/share-api/accounts',{});const j=await r.json();if(!r.ok)throw Error(j.error||'Falha ao consultar contas');$('#account').innerHTML='';for(const a of j.accounts||[]){const o=document.createElement('option');o.value=a.id||a.account;o.textContent=a.name||a.username||a.account;$('#account').append(o)}status('Contas carregadas. Escolha o destino.')}catch(e){status('Não consegui carregar as contas: '+e.message)}});
$('#clear').addEventListener('click',async()=>{const d=await db();await new Promise((ok,no)=>{const tx=d.transaction('inbox','readwrite');tx.objectStore('inbox').clear();tx.oncomplete=ok;tx.onerror=()=>no(tx.error)});queue=[];localStorage.removeItem('editorial-pending-transfer');$('#pick').value='';render();status('Fila local limpa.');});
$('#send').addEventListener('click',async()=>{
 const button=$('#send');if(button.disabled)return;
 const files=queue.map(x=>x.file);
 if(!files.length)return status('Adicione ou compartilhe uma imagem primeiro.');
 if(!$('#key').value||!$('#account').value)return status('Informe a chave e selecione a conta.');
 if(files.reduce((n,f)=>n+f.size,0)>4*1024*1024)return status('Limite total: 4 MiB por envio.');
 if($('#format').value==='carousel'&&files.length<2)return status('Carrossel exige pelo menos 2 imagens.');
 if($('#format').value!=='carousel'&&files.length!==1)return status('Este formato aceita exatamente 1 arquivo.');
 button.disabled=true;status('Enviando…');
 try{
  const media=await Promise.all(files.map(async file=>({mime:file.type,base64:await toBase64(file)})));
  const fingerprint=JSON.stringify({conta:$('#account').value,format:$('#format').value,caption:$('#caption').value,media});
  const fingerprintHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(fingerprint)))).map(x=>x.toString(16).padStart(2,'0')).join('');
  let pending=null;try{pending=JSON.parse(localStorage.getItem('editorial-pending-transfer')||'null')}catch{}
  if(!pending||pending.fingerprintHash!==fingerprintHash){pending={fingerprintHash,id:'share_'+crypto.randomUUID().replaceAll('-','')};localStorage.setItem('editorial-pending-transfer',JSON.stringify(pending))}
  const payload={conta:$('#account').value,requestId:pending.id,transferApproved:true,format:$('#format').value,caption:$('#caption').value,media};
  const r=await api('/share-api/transfer',payload);const j=await r.json();
  if(!r.ok||j.error)throw Error(j.error||'Transferência recusada');
  const d=await db();await new Promise((ok,no)=>{const tx=d.transaction('inbox','readwrite');tx.objectStore('inbox').clear();tx.oncomplete=ok;tx.onerror=()=>no(tx.error)});
  queue=[];localStorage.removeItem('editorial-pending-transfer');render();$('#pick').value='';status('Enviado para revisão. Recibo: '+JSON.stringify(j));
 }catch(e){status('Falha: '+e.message+' — os arquivos permanecem na fila. Repetir sem alterar o conteúdo reutiliza o mesmo requestId.')}
 finally{button.disabled=false}
});
function toBase64(file){return new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=()=>no(r.error);r.readAsDataURL(file)})}
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(e=>status('Falha ao ativar compartilhamento: '+e.message));
loadQueue().then(()=>status(queue.length?'Arquivo recebido. Confira e envie para revisão.':'Pronto para receber uma imagem compartilhada.'));
