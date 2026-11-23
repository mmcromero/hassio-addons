import {useId,useRef,useState,type CSSProperties,type KeyboardEvent,type ReactNode} from 'react';
import './section-tabs.css';
type Section={id:string;label:string;content:ReactNode};
// Keep panels mounted so drafts, local controls and native validation survive
// navigation. The existing focusField helper opens a hidden aria-controls panel.
export default function SectionTabs({label,sections}:{label:string;sections:Section[]}){
 const prefix=useId(),[selected,setSelected]=useState(sections[0]?.id??'');
 const buttons=useRef<Record<string,HTMLButtonElement|null>>({});
 const active=sections.some(section=>section.id===selected)?selected:sections[0]?.id;
 const tabId=(id:string)=>prefix+'-tab-'+id;
 const panelId=(id:string)=>prefix+'-panel-'+id;
 const handleKey=(event:KeyboardEvent<HTMLButtonElement>,index:number)=>{
  let next:number;
  switch(event.key){
   case 'ArrowRight':next=(index+1)%sections.length;break;
   case 'ArrowLeft':next=(index+sections.length-1)%sections.length;break;
   case 'Home':next=0;break;
   case 'End':next=sections.length-1;break;
   default:return;
  }
  event.preventDefault();
  const id=sections[next].id;setSelected(id);buttons.current[id]?.focus();
 };
 if(!sections.length)return null;
 return <div className="section-tabs">
  <div role="tablist" aria-label={label} className="section-tab-list" style={{'--section-count':sections.length} as CSSProperties}>
   {sections.map((section,index)=><button type="button" key={section.id} id={tabId(section.id)} role="tab" aria-selected={active===section.id} aria-controls={panelId(section.id)} tabIndex={active===section.id?0:-1} ref={node=>{buttons.current[section.id]=node;}} onClick={()=>setSelected(section.id)} onKeyDown={event=>handleKey(event,index)}>{section.label}</button>)}
  </div>
  {sections.map(section=><div key={section.id} role="tabpanel" id={panelId(section.id)} aria-labelledby={tabId(section.id)} className="section-tab-panel" hidden={active!==section.id}>{section.content}</div>)}
 </div>;
}
