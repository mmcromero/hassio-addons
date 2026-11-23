import BrandIcon,{type BrandIconName} from './BrandIcon';

// UX-HEADER-001: one heading for Products and PDV, from laboratory revision a727594.
export default function ModuleHeading({symbol,title,description,id,action}:{symbol:BrandIconName;title:import('react').ReactNode;description?:string;id?:string;action?:import('react').ReactNode}){
 return <div className="ad-module-heading-row"><section className="ad-module-heading"><h1 id={id} tabIndex={-1} className="ad-module-title"><BrandIcon name={symbol}/>{title}</h1>{description&&<p className="ad-module-description">{description}</p>}</section>{action&&<div className="ad-module-heading-action">{action}</div>}</div>;
}
