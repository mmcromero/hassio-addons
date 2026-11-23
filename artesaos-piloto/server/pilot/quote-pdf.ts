import {PDFDocument,rgb,type PDFFont} from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';
import {readFileSync} from 'node:fs';
import type {DocumentData} from './quote-document.js';
const money=(n:number)=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(n/100);
export async function renderQuotePdf(id:number,edition:number,date:string,data:DocumentData,logo?:Buffer){
 const regular=readFileSync(new URL('../../assets/fonts/NotoSans-Regular.ttf',import.meta.url));
 const bold=readFileSync(new URL('../../assets/fonts/NotoSans-Bold.ttf',import.meta.url));
 const pdf=await PDFDocument.create();pdf.registerFontkit(fontkit);
 const font=await pdf.embedFont(regular,{subset:true}),heading=await pdf.embedFont(bold,{subset:true});
 const characters=new Map([[font,new Set(font.getCharacterSet())],[heading,new Set(heading.getCharacterSet())]]);
 let page=pdf.addPage([595.28,841.89]),y=795,pages=1;
 function next(){if(++pages>40)throw Error('Documento excede o limite de 40 páginas. Reduza as observações ou os itens.');page=pdf.addPage([595.28,841.89]);y=795;}
 function line(value:string,size=11,f:PDFFont=font){
  // Normalize controls; use a visible fallback for glyphs absent from the bundled font.
  const supported=characters.get(f)!;
  const clean=Array.from(String(value).replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g,' ')).map(c=>supported.has(c.codePointAt(0)!)?c:'?').join('');
  for(const paragraph of clean.split('\n')){
   let text='';
   for(const char of paragraph){if(f.widthOfTextAtSize(text+char,size)>499){draw(text);text='';}text+=char;}draw(text);
  }
  function draw(text:string){if(y<55)next();page.drawText(text,{x:48,y,size,font:f,color:rgb(.12,.18,.15)});y-=size+6;}
 }
 if(logo){const image=await pdf.embedPng(logo);const scale=Math.min(160/image.width,70/image.height);page.drawImage(image,{x:48,y:y-image.height*scale,width:image.width*scale,height:image.height*scale});y-=image.height*scale+26;}
 line(data.company.name,18,heading);line(`Responsável: ${data.company.responsible}`);line(`${data.company.phone} | ${data.company.email}`);y-=12;
 line(`Orçamento ${id} · Edição ${edition}`,16,heading);line(`Finalizado em: ${new Date(date).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'})}`);
 line(`Cliente: ${String(data.quote.client.name??'')}`);y-=12;
 for(const item of data.quote.items){line(item.name,12,heading);line(`${item.quantity} × ${money(item.prices[item.priceKey])} = ${money(Number(item.quantity)*item.prices[item.priceKey])}`);
  if(item.packaging==='with')line(`Embalagem: ${item.packagingType??''} · ${item.packagingIncluded?'incluída no preço':money(Math.round(Number(item.packagingAmount.replace(',','.'))*100))+' por unidade'}`);
  y-=7;
 }
 line(`Produtos: ${money(data.totals.productCents)}`);line(`Embalagens cobradas: ${money(data.totals.packagingCents)}`);line(`Frete: ${money(data.totals.deliveryCents)}`);line(`Total: ${money(data.totals.totalCents)}`,15,heading);
 line(`Entrega: ${data.quote.delivery.mode==='pickup'?'retirada no local':data.quote.delivery.mode==='courtesy'?'cortesia':data.quote.delivery.carrier}`);
 if(data.quote.delivery.notes)line(data.quote.delivery.notes);
 if(data.quote.notes){y-=10;line('Observações comerciais',12,heading);line(data.quote.notes);}
 const all=pdf.getPages();all.forEach((p,i)=>p.drawText(`${i+1} / ${all.length}`,{x:495,y:28,size:9,font}));
 return pdf.save();
}
