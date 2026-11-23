/** B9: fontes e histórico não podem ser apagados ou reescritos. */
export const attentionSql=`
CREATE INDEX material_deficit_scan ON material_movements(material_id,id) WHERE lot_id IS NULL;
CREATE INDEX client_stock_order ON stock_items(order_id) WHERE kind='client';
CREATE INDEX attention_target ON attention_events(state,kind,item_ref,location_id);
CREATE INDEX attention_source ON attention_events(kind,source_kind,source_id,state);
CREATE INDEX attention_history_event ON attention_history(attention_id,id);
CREATE TRIGGER attention_no_delete BEFORE DELETE ON attention_events BEGIN SELECT RAISE(ABORT,'Ocorrência histórica imutável'); END;
CREATE TRIGGER attention_origin_no_update BEFORE UPDATE OF occurrence_key,kind,source_kind,source_id,item_ref,location_id,details,action_href,created_at ON attention_events BEGIN SELECT RAISE(ABORT,'Origem de pendência imutável'); END;
`;
