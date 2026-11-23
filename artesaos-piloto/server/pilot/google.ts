import * as oidc from 'openid-client';
import type {PilotConfig} from './config.js';
import type {Identity} from './store.js';
export interface IdentityProvider{start(state:string,nonce:string,verifier:string):Promise<string>;complete(url:URL,state:string,nonce:string,verifier:string):Promise<Identity>}
export function googleProvider(config:PilotConfig,transport?:oidc.CustomFetch):IdentityProvider{
 let cached:Promise<oidc.Configuration>|undefined;
 const client=()=>cached??=oidc.discovery(new URL('https://accounts.google.com'),config.clientId,config.clientSecret,undefined,transport?{[oidc.customFetch]:transport}:undefined).then(c=>{oidc.enableNonRepudiationChecks(c);return c;}).catch(e=>{cached=undefined;throw e;});
 const redirectUri=new URL('auth/google/callback',config.publicUrl).href;
 return {
  async start(state,nonce,verifier){const c=await client();return oidc.buildAuthorizationUrl(c,{redirect_uri:redirectUri,scope:'openid email',state,nonce,code_challenge:await oidc.calculatePKCECodeChallenge(verifier),code_challenge_method:'S256',prompt:'select_account'}).href;},
  async complete(url,state,nonce,verifier){const expected=new URL('auth/google/callback',config.publicUrl);if(url.origin!==expected.origin||url.pathname!==expected.pathname||url.username||url.password||url.hash)throw Error('Callback de autenticação não autorizado.');const c=await client();const response=await oidc.authorizationCodeGrant(c,url,{pkceCodeVerifier:verifier,expectedState:state,expectedNonce:nonce,idTokenExpected:true});const claims=response.claims();if(!claims||claims.iss!=='https://accounts.google.com'||typeof claims.sub!=='string'||typeof claims.email!=='string'||claims.email_verified!==true)throw Error('Identidade Google não confirmada.');return {issuer:claims.iss,subject:claims.sub,email:claims.email,verified:true};}
 };
}
