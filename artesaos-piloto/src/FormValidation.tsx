import {useEffect,useRef,useState,type FormEvent,type FormHTMLAttributes} from 'react';
import {ActionFormContext} from './ActionButton';
export type ValidationIssue={element:HTMLElement;message:string};
let serial=0;
export function RequiredMark(){return <span className="required-mark" aria-hidden="true"> *</span>;}
function message(control:HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement){
 const v=control.validity;
 if(v.valueMissing)return 'Preencha este campo obrigatório.';
 if(v.typeMismatch)return control instanceof HTMLInputElement&&control.type==='email'?'Informe um e-mail válido.':'Confira o formato informado.';
 if(v.rangeUnderflow)return `Informe um valor maior ou igual a ${(control as HTMLInputElement).min}.`;
 if(v.rangeOverflow)return `Informe um valor menor ou igual a ${(control as HTMLInputElement).max}.`;
 if(v.stepMismatch)return 'Use um valor compatível com o incremento indicado.';
 if(v.tooLong)return 'O texto excede o tamanho permitido.';
 return 'Confira o valor ou formato informado neste campo.';
}
export function clearValidation(root:HTMLElement){
 root.querySelectorAll('[data-validation-message]').forEach(node=>node.remove());
 root.querySelectorAll<HTMLElement>('[data-validation-invalid]').forEach(node=>{const id=node.dataset.validationInvalid;node.removeAttribute('aria-invalid');const described=(node.getAttribute('aria-describedby')??'').split(' ').filter(value=>value&&value!==id);if(described.length)node.setAttribute('aria-describedby',described.join(' '));else node.removeAttribute('aria-describedby');delete node.dataset.validationInvalid;});
}
export function focusField(element:HTMLElement){
 for(let ancestor=element.parentElement;ancestor;ancestor=ancestor.parentElement){
  if(ancestor instanceof HTMLDetailsElement)ancestor.open=true;
  if(ancestor.hidden&&ancestor.id){const toggle=Array.from(document.querySelectorAll<HTMLElement>('[aria-controls]')).find(node=>node.getAttribute('aria-controls')===ancestor!.id);toggle?.click();}
 }
 requestAnimationFrame(()=>{element.focus();element.scrollIntoView({block:'center'});});
}
export function showValidation(root:HTMLElement,issues:ValidationIssue[]){
 clearValidation(root);if(!issues.length)return true;
 const ordered=issues.filter((item,index)=>issues.findIndex(other=>other.element===item.element)===index).sort((a,b)=>a.element===b.element?0:a.element.compareDocumentPosition(b.element)&Node.DOCUMENT_POSITION_FOLLOWING?-1:1);
 for(const issue of ordered){const id=`field-error-${++serial}`,note=document.createElement('p');note.id=id;note.className='field-error';note.dataset.validationMessage='true';note.textContent=issue.message;issue.element.setAttribute('aria-invalid','true');issue.element.dataset.validationInvalid=id;issue.element.setAttribute('aria-describedby',[issue.element.getAttribute('aria-describedby'),id].filter(Boolean).join(' '));const anchor=issue.element.closest('label')??issue.element;anchor.insertAdjacentElement('afterend',note);}
 focusField(ordered[0].element);return false;
}
export function validateFields(root:HTMLElement,additional:ValidationIssue[]=[],mode='save'){
 const issues:ValidationIssue[]=[...additional];
 for(const control of Array.from(root.querySelectorAll<HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement>('input,select,textarea'))){
  if(control.disabled||control.matches(':disabled')||control.closest('dialog')!==root.closest('dialog'))continue;
  if(control.willValidate&&!control.validity.valid)issues.push({element:control,message:message(control)});
  else if(control.getAttribute('aria-required')==='true'&&(!control.dataset.requiredFor||control.dataset.requiredFor===mode)&&!control.value.trim())issues.push({element:control,message:'Preencha este campo obrigatório.'});
 }
 for(const group of Array.from(root.querySelectorAll<HTMLElement>('[data-require-one]'))){
  const fields=Array.from(group.querySelectorAll<HTMLInputElement>(group.dataset.requireOne!)).filter(input=>!input.matches(':disabled')&&input.closest('dialog')===root.closest('dialog'));
  if(fields.length&&!fields.some(input=>input.value.trim()))issues.push({element:fields[0],message:group.dataset.requireMessage??'Preencha pelo menos um dos campos deste grupo.'});
 }
 for(const panel of Array.from(root.querySelectorAll<HTMLElement>('[data-pending-category]'))){if(panel.closest('dialog')!==root.closest('dialog'))continue;const input=panel.querySelector<HTMLInputElement>('input');if(input)issues.push({element:input.disabled?panel:input,message:'Conclua a criação da categoria ou cancele essa inclusão antes de salvar o produto.'});}
 return showValidation(root,issues);
}
export default function ValidatedForm({onSubmit,children,...props}:FormHTMLAttributes<HTMLFormElement>){
 const ref=useRef<HTMLFormElement>(null),locked=useRef(false);
 const [pending,setPending]=useState(false),[submitter,setSubmitter]=useState<HTMLElement|null>(null),[actionError,setActionError]=useState(false);
 useEffect(()=>{
  const form=ref.current!;
  const annotate=()=>{for(const control of Array.from(form.querySelectorAll<HTMLInputElement>('[required],[aria-required=true]'))){const label=control.labels?.[0];if(label&&!label.querySelector('.required-mark')&&!label.textContent?.includes('*')){const mark=document.createElement('span');mark.className='required-mark';mark.setAttribute('aria-hidden','true');mark.textContent=' *';if(label.contains(control)){let anchor:HTMLElement=control;while(anchor.parentElement!==label)anchor=anchor.parentElement!;label.insertBefore(mark,anchor);}else label.append(mark);}}};
  annotate();const observer=new MutationObserver(annotate);observer.observe(form,{childList:true,subtree:true,attributes:true,attributeFilter:['required','aria-required']});return()=>observer.disconnect();
 },[]);
 return <ActionFormContext.Provider value={{pending,submitter}}><form {...props} ref={ref} noValidate aria-busy={pending||undefined} onSubmit={event=>{
  event.preventDefault();if(locked.current||!validateFields(event.currentTarget))return;
  setActionError(false);setSubmitter(((event.nativeEvent as SubmitEvent).submitter as HTMLElement|null)??event.currentTarget.querySelector<HTMLElement>('button:not([type=button])'));
  try{const result=(onSubmit as ((event:FormEvent<HTMLFormElement>)=>unknown)|undefined)?.(event);
   if(result&&typeof (result as PromiseLike<unknown>).then==='function'){
    locked.current=true;setPending(true);Promise.resolve(result).catch(()=>setActionError(true)).finally(()=>{locked.current=false;setPending(false);});
   }
  }catch{setActionError(true);}
 }}><p className="required-note">* Indica preenchimento obrigatório conforme a regra do campo ou grupo.</p>{children}{actionError&&<p role="alert" className="field-error">Não foi possível confirmar o envio. Confira os dados e tente novamente.</p>}</form></ActionFormContext.Provider>;
}
