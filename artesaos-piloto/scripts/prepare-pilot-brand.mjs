import {existsSync,copyFileSync,mkdirSync,readFileSync,rmSync} from 'node:fs';
import {resolve} from 'node:path';
for(const [name,target] of [['logo_principal.png','pilot-logo.png'],['logo_horizontal_negativa.png','pilot-logo-horizontal.png']]){
 const source=[`pilot/branding/${name}`,`branding/${name}`,...(target==='pilot-logo.png'?['pilot/branding/logo.png','branding/logo.png']:[])].map(p=>resolve(p)).find(existsSync);
 const destination=resolve('dist',target);
 if(!source){rmSync(destination,{force:true});continue;}
 const file=readFileSync(source);
 if(file.length>2*1024*1024||!file.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))throw Error('A logo deve ser PNG de até 2 MB.');
 mkdirSync('dist',{recursive:true});copyFileSync(source,destination);
}

// Reuse the existing small-space symbol, preserving the official brand.
const {PNG}=await import('pngjs');
const symbol=['pilot/branding/simbolo.png','branding/simbolo.png'].map(p=>resolve(p)).find(existsSync);
if(!symbol)throw Error('Símbolo oficial necessário para os ícones PWA.');
const sourceIcon=PNG.sync.read(readFileSync(symbol));
for(const size of [192,512]){
 const image=new PNG({width:size,height:size});
 for(let i=0;i<image.data.length;i+=4){image.data[i]=245;image.data[i+1]=242;image.data[i+2]=233;image.data[i+3]=255;}
 const scale=size*0.84/Math.max(sourceIcon.width,sourceIcon.height),width=Math.round(sourceIcon.width*scale),height=Math.round(sourceIcon.height*scale),left=Math.floor((size-width)/2),top=Math.floor((size-height)/2);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const sx=Math.min(sourceIcon.width-1,Math.floor(x/scale)),sy=Math.min(sourceIcon.height-1,Math.floor(y/scale)),from=(sy*sourceIcon.width+sx)*4,to=((top+y)*size+left+x)*4,alpha=sourceIcon.data[from+3]/255;
  for(let c=0;c<3;c++)image.data[to+c]=Math.round(sourceIcon.data[from+c]*alpha+image.data[to+c]*(1-alpha));
 }
 // Existing runtime Dockerfiles copy dist/assets; no new mount or COPY contract.
 mkdirSync(resolve('dist/assets'),{recursive:true});
 const {writeFileSync}=await import('node:fs');writeFileSync(resolve('dist/assets',`pilot-pwa-${size}.png`),PNG.sync.write(image));
}
