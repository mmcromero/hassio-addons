"""Testes locais sem Evolution, HA, n8n, rede ou Actions."""
import unittest
from evolution_adapter import normalize_evolution

def event():
    return {
        "event": "messages.upsert", "instance": "umdoislab",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False, "id": "msg-123"},
            "pushName": "Cliente",
            "message": {"conversation": "Olá"},
        },
    }

class EvolutionAdapterTests(unittest.TestCase):
    def test_text(self):
        result = normalize_evolution(event())
        self.assertEqual(result["messageText"], "Olá")
        self.assertEqual(result["senderId"], "5511999999999@s.whatsapp.net")
        self.assertTrue(result["isClientMessage"])

    def test_extended_text(self):
        payload = event()
        payload["data"]["message"] = {"extendedTextMessage": {"text": "Preço?"}}
        self.assertEqual(normalize_evolution(payload)["messageText"], "Preço?")

    def test_rejects_own_message(self):
        payload = event()
        payload["data"]["key"]["fromMe"] = True
        self.assertIsNone(normalize_evolution(payload))

    def test_rejects_group(self):
        payload = event()
        payload["data"]["key"]["remoteJid"] = "1203630@g.us"
        self.assertIsNone(normalize_evolution(payload))

    def test_rejects_wrong_instance(self):
        payload = event()
        payload["instance"] = "outra"
        self.assertIsNone(normalize_evolution(payload))

    def test_rejects_other_event(self):
        payload = event()
        payload["event"] = "messages.update"
        self.assertIsNone(normalize_evolution(payload))

    def test_rejects_empty_text(self):
        payload = event()
        payload["data"]["message"]["conversation"] = " "
        self.assertIsNone(normalize_evolution(payload))

    def test_rejects_malformed_data(self):
        self.assertIsNone(normalize_evolution({"event": "messages.upsert", "instance": "umdoislab"}))

if __name__ == "__main__":
    unittest.main()
