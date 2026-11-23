export const CLIENT_CATEGORY='Produtos de cliente';
export const productCategory=(product:{origin:string;category?:string})=>product.origin==='client'?CLIENT_CATEGORY:(product.category??'').trim();
