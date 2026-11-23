/** Intervalo entre consultas: 3 s no começo, 10 s depois; para de vez após o limite. */
export const POLL_FAST_MS=3000,POLL_SLOW_MS=10000,POLL_FAST_COUNT=20,POLL_LIMIT_MS=16*60000;
export function nextPollDelay(attempt:number){return attempt<POLL_FAST_COUNT?POLL_FAST_MS:POLL_SLOW_MS;}
export type ChargeStatus={id:string;status:'pending'|'approved'|'closed';amountCents:number};
/** Resultado de uma consulta, já comparado com o valor esperado da venda. */
export function judgeCharge(result:ChargeStatus,expectedCents:number):'waiting'|'paid'|'closed'|'mismatch'{
 if(result.amountCents!==expectedCents)return 'mismatch';
 if(result.status==='approved')return 'paid';
 return result.status==='pending'?'waiting':'closed';
}
