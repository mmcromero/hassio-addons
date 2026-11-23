import type {ReactNode,Ref} from 'react';
import BrandIcon,{type BrandIconName} from './BrandIcon';
import './module-heading.css';

// UX-HEADER-001: one module heading and one geometry for authenticated modules.
export default function ModuleHeading({symbol,title,description,id,action,headingRef}:{symbol:BrandIconName;title:ReactNode;description?:string;id?:string;action?:ReactNode;headingRef?:Ref<HTMLHeadingElement>}){
 return <div className="ad-module-heading-row"><div className="ad-module-heading"><h1 ref={headingRef} id={id} tabIndex={-1} className="ad-module-title"><BrandIcon name={symbol}/><span className="ad-module-title-text">{title}</span></h1>{description&&<p className="ad-module-description">{description}</p>}</div>{action&&<div className="ad-module-heading-action">{action}</div>}</div>;
}
