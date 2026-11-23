import ActionButton from './ActionButton';
import type {ButtonHTMLAttributes} from 'react';

export default function ListEditButton(props:ButtonHTMLAttributes<HTMLButtonElement>){
 return <ActionButton {...props} type="button" className="list-edit" aria-label="Editar" title="Editar"><span className="list-edit-text">Editar</span><svg className="list-edit-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m16 3 5 5-12 12-6 1 1-6Z"/><path d="m14 5 5 5"/></svg></ActionButton>;
}
