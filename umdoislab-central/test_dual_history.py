"""Regressões offline para histórico de número e LID alternativo."""
import unittest
from datetime import datetime, timezone
from evolution_history import collect_both

SENDER = "5511999999999@s.whatsapp.net"
NOW = datetime(2026, 11, 20, 7, 0, tzinfo=timezone.utc)
SINCE = "2026-11-20T06:00:00+00:00"


def record(mid, *, alternate=False, from_me=False, stamp=1795172500):
    key = {"remoteJid": "123456789012345@lid" if alternate else SENDER,
           "fromMe": from_me, "id": mid}
    if alternate:
        key["remoteJidAlt"] = SENDER
    return {"key": key, "messageTimestamp": stamp}


def page(records, n=1):
    return {"messages": {"total": len(records), "pages": 1,
                         "currentPage": n, "records": records}}


def reader(records):
    return lambda n: page(records, n)


class DualHistoryTests(unittest.TestCase):
    def test_lid_original_is_recognized(self):
        snap = collect_both(SENDER, SINCE,
                            reader([record("old")]),
                            reader([record("new", alternate=True)]), clock=NOW)
        self.assertTrue(snap["complete"])
        self.assertEqual({r["id"] for r in snap["inbound"]}, {"old", "new"})

    def test_alternate_empty_valid(self):
        snap = collect_both(SENDER, SINCE, reader([record("old")]),
                            reader([]), clock=NOW)
        self.assertEqual(len(snap["inbound"]), 1)

    def test_missing_alt_reader_blocks(self):
        self.assertIsNone(collect_both(SENDER, SINCE,
                                      reader([record("old")]), None, clock=NOW))

    def test_other_lid_alt_blocks(self):
        alt = record("new", alternate=True)
        alt["key"]["remoteJidAlt"] = "5511888888888@s.whatsapp.net"
        self.assertIsNone(collect_both(SENDER, SINCE,
                                      reader([]), reader([alt]), clock=NOW))

    def test_other_jid_with_claimed_alt_blocks(self):
        alt = record("new", alternate=True)
        alt["key"]["remoteJid"] = "5511777777777@s.whatsapp.net"
        self.assertIsNone(collect_both(SENDER, SINCE,
                                      reader([]), reader([alt]), clock=NOW))

    def test_one_unavailable_partition_blocks(self):
        def broken(n):
            raise TimeoutError()
        self.assertIsNone(collect_both(SENDER, SINCE,
                                      reader([]), broken, clock=NOW))

    def test_conflicting_dupe_blocks(self):
        p = record("same", from_me=False)
        a = record("same", alternate=True, from_me=True)
        self.assertIsNone(collect_both(SENDER, SINCE,
                                      reader([p]), reader([a]), clock=NOW))

    def test_equivalent_dupe_collapses(self):
        p = record("same")
        a = record("same", alternate=True)
        snap = collect_both(SENDER, SINCE,
                            reader([p]), reader([a]), clock=NOW)
        self.assertEqual(len(snap["inbound"]), 1)

    def test_duplicate_in_stream_without_identical_record_blocks(self):
        p = record("same")
        x = record("same", stamp=1795172501)
        self.assertIsNone(collect_both(SENDER, SINCE,
                                      reader([p, x]), reader([]), clock=NOW))


if __name__ == "__main__":
    unittest.main()


# Regressão LAB Evolution: ID duplicado de forma idêntica na partição
# principal e mensagem recente registrada apenas sob remoteJidAlt/LID.
class RealShapeRegression(unittest.TestCase):
    def test_duplicate_in_direct_and_new_original_in_lid(self):
        p = record("repeated", stamp=1795172400)
        copy = {**p, "id": "other-sql-row"}
        alias = record("new-message", alternate=True, stamp=1795172500)
        snap = collect_both(SENDER, SINCE, reader([p, copy]),
                            reader([alias]), clock=NOW)
        self.assertIsNotNone(snap)
        self.assertEqual({x["id"] for x in snap["inbound"]},
                         {"repeated", "new-message"})
