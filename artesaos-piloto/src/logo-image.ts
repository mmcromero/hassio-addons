// Inspect dimensions before allocating a decoded bitmap on a phone.
export function logoDimensions(bytes:Uint8Array):[number,number]{
 const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),text=(at:number,n:number)=>String.fromCharCode(...bytes.subarray(at,at+n));
 if(bytes.length>=24&&text(1,3)==='PNG')return [v.getUint32(16),v.getUint32(20)];
 if(bytes.length>=30&&text(0,4)==='RIFF'&&text(8,4)==='WEBP'){
  const kind=text(12,4);
  if(kind==='VP8X')return [1+bytes[24]+bytes[25]*256+bytes[26]*65536,1+bytes[27]+bytes[28]*256+bytes[29]*65536];
  if(kind==='VP8 '&&bytes[23]===157&&bytes[24]===1&&bytes[25]===42)return [v.getUint16(26,true)&16383,v.getUint16(28,true)&16383];
  if(kind==='VP8L'&&bytes[20]===47){const bits=v.getUint32(21,true);return [(bits&16383)+1,((bits>>>14)&16383)+1];}
 }
 if(bytes.length>4&&bytes[0]===255&&bytes[1]===216){
  let at=2;
  while(at+4<=bytes.length){
   if(bytes[at++]!==255)break;while(bytes[at]===255)at++;const marker=bytes[at++];
   if(marker===217||marker===218)break;if(marker===1||(marker>=208&&marker<=215))continue;
   if(at+2>bytes.length)break;const length=v.getUint16(at);if(length<2||at+length>bytes.length)break;
   if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)&&length>=7)return [v.getUint16(at+5),v.getUint16(at+3)];
   at+=length;
  }
 }
 throw Error('Não foi possível ler esta imagem. Escolha outro PNG, JPEG ou WebP.');
}
