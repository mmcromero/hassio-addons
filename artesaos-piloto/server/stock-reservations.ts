import type {DatabaseSync} from 'node:sqlite';
/** Projeção transacional, refeita das demandas ativas e somente da posse central. */
export function reservationsEnabled(db:DatabaseSync){return !!db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='stock_reservations'").get();}
export function refreshReservations(db:DatabaseSync){
 if(!reservationsEnabled(db))return;
 db.exec('DELETE FROM stock_reservations');
 const balances=new Map<string,number>();
 for(const line of db.prepare("SELECT l.*,o.created_at FROM order_lines l JOIN orders o ON o.id=l.order_id WHERE l.active=1 AND o.status NOT IN ('delivered','cancelled') ORDER BY o.created_at,o.rowid,l.rowid").all()){
  if(!line.product_id)continue;
  const product=db.prepare('SELECT data FROM products WHERE id=?').get(line.product_id);if(!product)continue;
  const own=JSON.parse(String(product.data)).origin==='own';
  const item=db.prepare('SELECT id FROM stock_items WHERE product_id=? AND kind=? AND '+(own?'order_id IS NULL':'order_id=?')).get(line.product_id,own?'own':'client',...(own?[]:[line.order_id]));if(!item)continue;
  const itemId=String(item.id);let available=balances.get(itemId);if(available===undefined)available=Math.max(0,Number(db.prepare("SELECT COALESCE(SUM(delta),0) n FROM product_stock_movements WHERE item_id=? AND location_id='central'").get(itemId)!.n));
  const quantity=Math.min(available,Number(line.quantity));if(quantity>0)db.prepare('INSERT INTO stock_reservations VALUES(?,?,?,?)').run(line.order_id,line.id,itemId,quantity);balances.set(itemId,available-quantity);
 }
}
export function reservedStock(db:DatabaseSync,itemId:string){return reservationsEnabled(db)?Number(db.prepare('SELECT COALESCE(SUM(quantity),0) n FROM stock_reservations WHERE item_id=?').get(itemId)!.n):0;}
