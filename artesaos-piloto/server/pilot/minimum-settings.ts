import type {DatabaseSync} from 'node:sqlite';
import {markupRanges} from '../manufacturing-model.js';
export function minimumSettings(data:Record<string,string>){
 const result={...data};
 for(const [key,range] of Object.entries(markupRanges)){
  const raw=result[key],number=raw?.trim()?Number(raw.replace(',','.')):NaN;
  if(!Number.isFinite(number)||number<range.min)result[key]=range.min.toFixed(1);
 }
 for(const key of ['energyHour','wearHour','humanHour'])if(!result[key]?.trim())result[key]='0';
 return result;
}
export function normalizeStoredMinimums(db:DatabaseSync){
 const row=db.prepare("SELECT data,revision FROM area_settings WHERE area='fabricacao'").get();
 const before:Record<string,string>=row?JSON.parse(String(row.data)):{};const after=minimumSettings(before);
 if(JSON.stringify(before)!==JSON.stringify(after))db.prepare("INSERT INTO area_settings(area,data,revision) VALUES ('fabricacao',?,?) ON CONFLICT(area) DO UPDATE SET data=excluded.data,revision=excluded.revision").run(JSON.stringify(after),Number(row?.revision??0)+1);
}
