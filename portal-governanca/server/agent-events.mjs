const EVENT_BLOCK=/<!--\s*AGENT_PROTOCOL_EVENT\s*-->\s*\x60{3}json\s*([\s\S]*?)\s*\x60{3}\s*<!--\s*\/AGENT_PROTOCOL_EVENT\s*-->/i;

export async function filterUnrecordedAgentEvents(events,ledger){
 const fresh=[];let alreadyRecorded=0;
 const stored=await ledger.listEvents({limit:500});
 const recorded=new Set(stored.events.map(row=>row.eventId).filter(Boolean));
 for(const event of Array.isArray(events)?events:[]){
  const body=typeof event?.body?.comment?.body==="string"?event.body.comment.body:"";
  const match=body.match(EVENT_BLOCK);
  let eventId="";
  if(match){try{const payload=JSON.parse(match[1]);eventId=typeof payload?.event_id==="string"?payload.event_id:"";}catch{}}
  if(eventId&&recorded.has(eventId)){alreadyRecorded++;continue;}
  fresh.push(event);
 }
 return{events:fresh,alreadyRecorded};
}
