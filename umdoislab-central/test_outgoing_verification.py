"""Verificação de evento de saída da Evolution sem conexão de rede."""
import json
import unittest
from outgoing_verification import verify_outgoing

SENDER = "5511999999999@s.whatsapp.net"
MID = "3EB0-valid-01"


def record(mid=MID, sender=SENDER, from_me=True, row_id=1, timestamp=1795154160,
           message="conteudo de teste"):
    return {"id": row_id, "key": {"id": mid, "remoteJid": sender, "fromMe": from_me},
            "messageTimestamp": timestamp, "message": {"conversation": message}}


def payload(records):
    return {"messages": {"total": len(records), "pages": 1, "currentPage": 1, "records": records}}


class Response:
    status = 200

    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.data[:limit]


class VerifyTests(unittest.TestCase):
    def check(self, data, **kwargs):
        def opener(request, timeout):
            self.assertEqual(request.method, "POST")
            self.assertIn(b'"id": "3EB0-valid-01"', request.data)
            self.assertTrue(any(header.lower() == "apikey" for header in request.headers))
            return Response(data)
        return verify_outgoing(SENDER, MID, base_url="http://localhost:8080",
                               instance="umdoislab", api_key="not-a-real-key",
                               opener=opener, **kwargs)

    def test_exact_confirmed_event(self):
        self.assertTrue(self.check(payload([record()])))

    def test_duplicate_sql_rows_with_identical_message(self):
        self.assertTrue(self.check(payload([record(row_id=1), record(row_id=2)])))

    def test_duplicate_rows_with_different_content_block(self):
        self.assertFalse(self.check(payload([record(row_id=1), record(row_id=2, message="diferente")])))

    def test_wrong_sender(self):
        self.assertFalse(self.check(payload([record(sender="5511888888888@s.whatsapp.net")])))

    def test_wrong_message_id(self):
        self.assertFalse(self.check(payload([record(mid="3EB0-other")])))

    def test_from_me_false(self):
        self.assertFalse(self.check(payload([record(from_me=False)])))

    def test_zero_results(self):
        self.assertFalse(self.check(payload([])))

    def test_missing_page_contract(self):
        self.assertFalse(self.check({"data": [record()]}))

    def test_incomplete_records(self):
        data=payload([record()])
        data["messages"]["total"]=2
        self.assertFalse(self.check(data))

    def test_invalid_message_timestamp(self):
        self.assertFalse(self.check(payload([record(timestamp=None)])))

    def test_unavailable_service(self):
        def unavailable(request, timeout):
            raise TimeoutError("read-only test timeout")
        self.assertFalse(verify_outgoing(SENDER,MID,base_url="http://localhost",
                        instance="umdoislab",api_key="dummy",opener=unavailable))

    def test_invalid_input_does_not_call_network(self):
        def forbidden(request, timeout):
            self.fail("network should not be called")
        self.assertFalse(verify_outgoing("not-jid",MID,base_url="http://localhost",
                         instance="umdoislab",api_key="dummy",opener=forbidden))


if __name__=="__main__":
    unittest.main()
