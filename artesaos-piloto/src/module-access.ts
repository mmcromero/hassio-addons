import {appName} from './branding';
import {moduleKeys,viewModule,type ModuleKey} from '../server/module-access';
export function enabledModules():ModuleKey[]{
 if(appName!=='Artesão Digital')return [...moduleKeys];
 const meta=document.querySelector<HTMLMetaElement>('meta[name="pilot-modules"]');
 // Older/offline read-only shells retain their existing behavior. APIs always recheck grants.
 return meta?meta.content.split(',').filter((key):key is ModuleKey=>moduleKeys.includes(key as ModuleKey)):[...moduleKeys];
}
export function moduleEnabled(key:ModuleKey){return enabledModules().includes(key);}
export function viewEnabled(view:string){const key=viewModule(view);return !key||moduleEnabled(key);}
