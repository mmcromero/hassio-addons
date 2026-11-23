/** B10 aditiva: preparo físico integral, distinto de cotação e entrega. */
export const shippingSql=`
CREATE TABLE shipment_preparations(
 id TEXT PRIMARY KEY,order_id TEXT NOT NULL UNIQUE REFERENCES orders(id),
 order_revision INTEGER NOT NULL,snapshot TEXT NOT NULL,actor TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE TRIGGER shipment_no_update BEFORE UPDATE ON shipment_preparations BEGIN SELECT RAISE(ABORT,'Preparo histórico imutável'); END;
CREATE TRIGGER shipment_no_delete BEFORE DELETE ON shipment_preparations BEGIN SELECT RAISE(ABORT,'Preparo histórico imutável'); END;
`;
