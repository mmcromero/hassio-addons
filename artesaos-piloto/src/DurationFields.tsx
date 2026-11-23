import {useState} from 'react';
import {durationParts,durationSeconds,type DurationInput} from '../server/manufacturing-model';
export default function DurationFields({value,onChange,prefix,label}:{value:number|null;onChange:(seconds:number|null)=>void;prefix:string;label:string}){
 const [parts,setParts]=useState<DurationInput>(()=>{const initial=durationParts(value);return {hours:value===null?'':String(initial.hours),minutes:value===null?'':String(initial.minutes),seconds:value===null?'':String(initial.seconds)};});
 const seconds=durationSeconds(parts),invalid=Object.values(parts).some(v=>v!=='')&&seconds===null;
 return <fieldset className="duration-fields"><legend>{label}</legend>{(['hours','minutes','seconds'] as const).map((part,i)=><label key={part} htmlFor={`${prefix}-${part}`}>{['Horas','Minutos','Segundos'][i]}<input id={`${prefix}-${part}`} type="number" min="0" max={part==='hours'?999999:59} step="1" value={parts[part]} aria-invalid={invalid||undefined} onChange={e=>{const next={...parts,[part]:e.target.value};setParts(next);onChange(durationSeconds(next));}}/></label>)}<p>{seconds===null?'Tempo pendente':(seconds/3600).toLocaleString('pt-BR',{maximumFractionDigits:6})+' horas decimais no cálculo'}. Aceita mais de 24 horas.</p>{invalid&&<p role="alert">Use horas inteiras e minutos/segundos entre 0 e 59.</p>}</fieldset>;
}
