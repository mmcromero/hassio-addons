"""Testes offline do coletor; nunca consulta a Evolution real."""
import unittest
from datetime import datetime, timezone
from evolution_history import collect

SENDER="5511999999999@s.whatsapp.net"
NOW=datetime(2026,11,20,6,0,tzinfo=timezone.utc)
SINCE="2026-11-20T05:55:00+00:00"


def entry(mid,stamp=1795154160,from_me=False,sender=SENDER):
    return {"key":{"remoteJid":sender,"id":mid,"fromMe":from_me},
            "messageTimestamp":stamp}


def page(records,total=None,pages=1,current=1):
    return {"messages":{"records":records,"total":len(records) if total is None else total,
                         "pages":pages,"currentPage":current}}


class HistoryTests(unittest.TestCase):
    def run_collection(self,records):
        return collect(SENDER,SINCE,lambda p:page(records),clock=NOW)

    def test_complete(self):
        snap=self.run_collection([entry("in1"),entry("out1",from_me=True)])
        self.assertTrue(snap["complete"])
        self.assertEqual([x["id"] for x in snap["outbound"]],["out1"])
        self.assertEqual([x["id"] for x in snap["inbound"]],["in1"])

    def test_two_pages(self):
        pages={1:page([entry("in1")],total=2,pages=2,current=1),
               2:page([entry("out1",from_me=True)],total=2,pages=2,current=2)}
        snap=collect(SENDER,SINCE,lambda p:pages[p],clock=NOW)
        self.assertTrue(snap["complete"])

    def test_page_missing(self):
        self.assertIsNone(collect(SENDER,SINCE,lambda p:page([],total=2),clock=NOW))

    def test_count_changed_blocks(self):
        pages={1:page([entry("in1")],total=2,pages=2,current=1),
               2:page([entry("out1")],total=3,pages=2,current=2)}
        self.assertIsNone(collect(SENDER,SINCE,lambda p:pages[p],clock=NOW))

    def test_other_chat_or_lid_blocks(self):
        self.assertIsNone(self.run_collection([entry("x",sender="other@lid")]))

    def test_missing_message_id_blocks(self):
        self.assertIsNone(self.run_collection([entry("")]))

    def test_identical_duplicate_is_deduplicated(self):
        result=self.run_collection([entry("x"),entry("x")])
        self.assertIsNotNone(result)
        self.assertEqual(len(result["inbound"]),1)

    def test_duplicate_whatsapp_message_with_different_db_row_ids(self):
        left={**entry("x"),"id":"database-row-91"}
        right={**entry("x"),"id":"database-row-92"}
        result=self.run_collection([left,right])
        self.assertIsNotNone(result)
        self.assertEqual(len(result["inbound"]),1)

    def test_duplicate_whatsapp_message_with_different_content_blocks(self):
        left={**entry("x"),"id":"database-row-91","message":{"conversation":"A"}}
        right={**entry("x"),"id":"database-row-92","message":{"conversation":"B"}}
        self.assertIsNone(self.run_collection([left,right]))

    def test_duplicate_id_with_conflicting_timestamp_blocks(self):
        self.assertIsNone(self.run_collection([entry("x"),entry("x",stamp=1795154170)]))

    def test_duplicate_id_with_conflicting_direction_blocks(self):
        self.assertIsNone(self.run_collection([entry("x"),entry("x",from_me=True)]))

    def test_missing_timestamp_blocks(self):
        self.assertIsNone(self.run_collection([entry("x",stamp=None)]))

    def test_failure_blocks(self):
        def fail(page_num):
            raise TimeoutError()
        self.assertIsNone(collect(SENDER,SINCE,fail,clock=NOW))

    def test_empty_history_is_complete_but_reconciler_must_reject_missing_original(self):
        snap=self.run_collection([])
        self.assertEqual(snap["inbound"],[])

    def test_no_unverified_schema(self):
        self.assertIsNone(collect(SENDER,SINCE,lambda p:{"data":[]},clock=NOW))


if __name__=="__main__":
    unittest.main()
