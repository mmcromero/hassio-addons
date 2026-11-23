import {createContext,forwardRef,useContext,useEffect,useRef,useState,type ButtonHTMLAttributes,type MouseEvent} from 'react';

export const ActionFormContext=createContext<{pending:boolean;submitter:HTMLElement|null}>({pending:false,submitter:null});
type Props=Omit<ButtonHTMLAttributes<HTMLButtonElement>,'onClick'>&{onClick?:(event:MouseEvent<HTMLButtonElement>)=>unknown;busy?:boolean};
/** Tracks the action's actual Promise, independently of other buttons or API calls. */
const ActionButton=forwardRef<HTMLButtonElement,Props>(function ActionButton({onClick,busy=false,disabled,children,...props},ref){
 const [pending,setPending]=useState(false),[error,setError]=useState(false),locked=useRef(false),node=useRef<HTMLButtonElement|null>(null),mounted=useRef(true),form=useContext(ActionFormContext);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const submitting=form.pending&&(props.type??'submit')==='submit';
 const waiting=pending||busy||(submitting&&form.submitter===node.current);
 return <><button {...props} ref={value=>{node.current=value;if(typeof ref==='function')ref(value);else if(ref)ref.current=value;}} disabled={disabled||waiting||submitting} aria-busy={waiting||undefined} data-action-pending={waiting?'true':undefined} onClick={event=>{
  if(disabled||locked.current||busy||submitting){event.preventDefault();return;}
  if(!onClick)return;
  setError(false);
  try{
   const result=onClick(event);
   if(result&&typeof (result as PromiseLike<unknown>).then==='function'){
    locked.current=true;setPending(true);
    Promise.resolve(result).catch(()=>{if(mounted.current)setError(true);}).finally(()=>{locked.current=false;if(mounted.current)setPending(false);});
   }
  }catch{event.preventDefault();setError(true);}
 }}>{waiting&&<span className="action-wait-mark" aria-hidden="true">◌ </span>}{children}</button>{waiting&&<span className="sr-only" role="status">Processando ação…</span>}{error&&<span className="field-error" role="alert">Não foi possível confirmar a operação. Verifique sua conexão e tente novamente.</span>}</>;
});
export default ActionButton;
