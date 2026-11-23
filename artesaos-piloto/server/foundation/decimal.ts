/** Escalas novas: dinheiro 2 casas, quantidade 6, custo unitário 8. Não altera o cálculo legado. */
export const scales={money:2,quantity:6,unitCost:8} as const;
const factor=(scale:number)=>{if(!Number.isInteger(scale)||scale<0||scale>12)throw Error('Escala inválida.');return 10n**BigInt(scale);};
export function parseDecimal(input:string,scale:number):bigint{
 factor(scale);
 if(typeof input!=='string'||input.length>100||!/^[-+]?\d+(?:[.,]\d+)?$/.test(input.trim()))throw Error('Decimal inválido.');
 const raw=input.trim().replace(',','.'),negative=raw.startsWith('-'),parts=raw.replace(/^[-+]/,'').split('.'),fraction=parts[1]??'';
 if(fraction.length>scale)throw Error('Precisão maior que a permitida.');
 const value=BigInt(parts[0])*factor(scale)+BigInt(fraction.padEnd(scale,'0')||'0');return negative?-value:value;
}
export function formatDecimal(value:bigint,scale:number):string{
 const unit=factor(scale),absolute=value<0n?-value:value;
 return `${value<0n?'-':''}${absolute/unit}${scale?'.'+String(absolute%unit).padStart(scale,'0'):''}`;
}
/** Arredondamento de metade para longe de zero, também para estornos. */
export function divideRounded(numerator:bigint,denominator:bigint):bigint{
 if(denominator===0n)throw Error('Divisão por zero.');
 const negative=(numerator<0n)!==(denominator<0n),n=numerator<0n?-numerator:numerator,d=denominator<0n?-denominator:denominator;
 const result=n/d+(2n*(n%d)>=d?1n:0n);return negative?-result:result;
}
export function rescale(value:bigint,from:number,to:number):bigint{return divideRounded(value*factor(to),factor(from));}
export function safeInteger(value:bigint):number{const result=Number(value);if(!Number.isSafeInteger(result))throw Error('Valor excede o limite seguro.');return result;}
