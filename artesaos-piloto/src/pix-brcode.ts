/** Pix "copia e cola" (BR Code estático com valor). Gerado localmente: sem API, sem banco, sem custo. */

export type PixReceiver={key:string;name:string;city:string};

/** CRC16-CCITT (poly 0x1021, init 0xFFFF), como exige o padrão EMV/BR Code. */
export function crc16(text:string){
 let crc=0xFFFF;
 for(const char of text){
  crc^=char.charCodeAt(0)<<8;
  for(let i=0;i<8;i++)crc=crc&0x8000?((crc<<1)^0x1021)&0xFFFF:(crc<<1)&0xFFFF;
 }
 return crc.toString(16).toUpperCase().padStart(4,'0');
}

/** Normaliza telefone BR, CPF/CNPJ, e-mail e chave aleatória (mesma regra usada no servidor). */
export function normalizePixKey(value:string){
 const key=value.trim();
 if(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(key))return key.toLowerCase();
 if(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(key))return key.toLowerCase();
 if(!/^[+\d ()./-]+$/.test(key))return key;
 const digits=key.replace(/\D/g,'');
 if(key.startsWith('+'))return '+'+digits;
 if((digits.length===11||digits.length===14)&&validDocument(digits))return digits;
 if((digits.length===10&&/^[1-9]\d[2-5]/.test(digits))||(digits.length===11&&/^[1-9]\d9/.test(digits)))return '+55'+digits;
 if((digits.length===12||digits.length===13)&&digits.startsWith('55'))return '+'+digits;
 return digits.length===11||digits.length===14?digits:key;
}
function validDocument(value:string){
 if(!/^\d{11}$|^\d{14}$/.test(value)||/^(\d)\1+$/.test(value))return false;
 const digits=[...value].map(Number),length=digits.length,base=length-2;
 const check=(n:number)=>{const weights=length===11?Array.from({length:n},(_,i)=>n+1-i):Array.from({length:n},(_,i)=>(n-1-i)%8+2);const remainder=digits.slice(0,n).reduce((sum,d,i)=>sum+d*weights[i],0)%11;return remainder<2?0:11-remainder;};
 return check(base)===digits[base]&&check(base+1)===digits[base+1];
}
export function validPixKey(value:string){
 if(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)&&value.length<=77)return true;
 if(/^\+[1-9]\d{9,14}$/.test(value))return true;
 if(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value))return true;
 return validDocument(value);
}

const field=(id:string,value:string)=>id+String(value.length).padStart(2,'0')+value;
/** Remove acentos e símbolos: o BR Code aceita apenas texto ASCII simples nesses campos. */
export function asciiText(value:string,max:number){
 return value.normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^A-Za-z0-9 ]/g,' ').replace(/\s+/g,' ').trim().toUpperCase().slice(0,max).trim();
}
/** Identificador da cobrança: só letras e números, até 25 caracteres. */
export function pixTxid(seed:string){return seed.replace(/[^A-Za-z0-9]/g,'').slice(0,25)||'***';}

/** Monta o texto "copia e cola" (e o conteúdo do QR). `amountCents` > 0, em centavos. */
export function pixPayload(receiver:PixReceiver,amountCents:number,txid='***'){
 const key=normalizePixKey(receiver.key),name=asciiText(receiver.name,25),city=asciiText(receiver.city,15);
 if(!validPixKey(key))throw Error('Chave Pix inválida. Confira a chave cadastrada.');
 if(!name)throw Error('Informe o nome do recebedor.');
 if(!city)throw Error('Informe a cidade do recebedor.');
 if(!Number.isInteger(amountCents)||amountCents<=0||amountCents>99999999999)throw Error('Informe um valor maior que zero.');
 const account=field('00','br.gov.bcb.pix')+field('01',key);
 const body=field('00','01')+field('01','11')+field('26',account)+field('52','0000')+field('53','986')+field('54',(amountCents/100).toFixed(2))+field('58','BR')+field('59',name)+field('60',city)+field('62',field('05',txid==='***'?'***':pixTxid(txid)))+'6304';
 return body+crc16(body);
}
