import {useRef,useState} from 'react';
import {logoDimensions} from './logo-image';
/** Reuses the logo's browser decode/canvas path. No original/EXIF is uploaded. */
export async function prepareProductImage(file:File){
 if(file.size>8*1024*1024||!file.size)throw Error('Escolha uma foto de até 8 MB.');
 const [w,h]=logoDimensions(new Uint8Array(await file.arrayBuffer()));
 if(!w||!h||w>8192||h>8192||w*h>24000000)throw Error('Foto grande demais em pixels. Use até 24 megapixels e 8192 pixels por lado.');
 let bitmap:ImageBitmap;try{bitmap=await createImageBitmap(file);}catch{throw Error('Não foi possível ler esta foto. Escolha outro PNG, JPEG ou WebP válido.');}
 try{
  if(bitmap.width>8192||bitmap.height>8192||bitmap.width*bitmap.height>24000000)throw Error('Foto grande demais em pixels.');
  const scale=Math.min(1,1024/bitmap.width,1024/bitmap.height),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));
  const ctx=canvas.getContext('2d');if(!ctx)throw Error('Não foi possível preparar a foto neste navegador.');ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
  let data=canvas.toDataURL('image/png');
  while(data.length>682000&&Math.max(canvas.width,canvas.height)>128){const smaller=document.createElement('canvas');smaller.width=Math.max(1,Math.floor(canvas.width*.75));smaller.height=Math.max(1,Math.floor(canvas.height*.75));smaller.getContext('2d')!.drawImage(canvas,0,0,smaller.width,smaller.height);canvas.width=smaller.width;canvas.height=smaller.height;ctx.drawImage(smaller,0,0);data=canvas.toDataURL('image/png');}
  if(data.length>682000)throw Error('Não foi possível reduzir a foto para 500 KB. Escolha outra imagem.');
  return data.split(',')[1];
 }finally{bitmap.close();}
}
export default function ProductImagePicker({value,disabled=false,onChange,onBusyChange}:{value:string;disabled?:boolean;onChange:(url:string)=>void;onBusyChange?:(busy:boolean)=>void}){
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(false);const lock=useRef(false);
 async function select(file?:File){if(!file||lock.current||disabled)return;lock.current=true;setBusy(true);onBusyChange?.(true);setError(false);setMessage('Preparando e enviando foto…');
  try{const png=await prepareProductImage(file);const response=await fetch(new URL('api/product-photos',document.baseURI),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({png}),signal:AbortSignal.timeout(30000)});if(!response.ok)throw Error(response.status===413?'A foto excedeu o limite permitido.':'Não foi possível enviar a foto. A foto anterior foi preservada. Tente novamente.');const data=await response.json();if(!/^api\/product-photos\/[a-f0-9]{32}\/[a-f0-9]{64}\.png$/.test(data.url))throw Error('Envio não confirmado. Tente novamente.');onChange(data.url);setMessage('Foto enviada. Salve o cadastro para confirmar esta foto no produto.');}
  catch(e){setError(true);setMessage(e instanceof Error?e.message:'Não foi possível preparar a foto. Escolha outra imagem.');}finally{lock.current=false;setBusy(false);onBusyChange?.(false);}
 }
 return <section aria-label="Foto do produto"><h3>Foto do produto</h3>{value&&<img alt="Prévia da foto do produto" src={/^api\/product-photos\/[a-f0-9]{32}\/[a-f0-9]{64}\.png$/.test(value)?new URL(value,document.baseURI).href:value} referrerPolicy="no-referrer" style={{maxWidth:180,maxHeight:180,objectFit:'contain'}}/>}<label>Selecionar foto<input type="file" accept="image/png,image/jpeg,image/webp" disabled={disabled||busy} aria-busy={busy||undefined} onChange={e=>{const file=e.target.files?.[0];e.target.value='';void select(file);}}/></label><p>PNG, JPEG ou WebP até 8 MB e 24 megapixels. Redução automática para até 1024 pixels por lado e 500 KB, sem ampliar a foto.</p>{/^https:\/\//.test(value)&&<p>Foto externa antiga preservada. Para substituí-la, selecione uma imagem.</p>}{message&&<p role={error?'alert':'status'}>{message}</p>}</section>;
}
