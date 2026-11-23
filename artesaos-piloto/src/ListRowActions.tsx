import ActionButton from './ActionButton';
import ListEditButton from './ListEditButton';

export default function ListRowActions({disabled=false,onEdit,onArchive}:{disabled?:boolean;onEdit:()=>void;onArchive:()=>void}){
 return <div className="list-row-actions">
  <ListEditButton disabled={disabled} onClick={onEdit}/>
  <ActionButton type="button" className="list-archive" aria-label="Arquivar" title="Arquivar" disabled={disabled} onClick={onArchive}>
   <span className="list-archive-text">Arquivar</span>
   <svg className="list-archive-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3h18v4H3zM5 7v14h14V7M10 11h4"/></svg>
  </ActionButton>
 </div>;
}
