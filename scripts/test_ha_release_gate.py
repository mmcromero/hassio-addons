import importlib.util
import pathlib
import unittest

p = pathlib.Path(__file__).with_name("ha_release_gate.py")
spec = importlib.util.spec_from_file_location("gate", p)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
REGISTRY = {"addons": [{"id": "factory-runner"}, {"id": "pager-virtual"}]}

class TestReleaseGate(unittest.TestCase):
    def check(self, decision, reason="", evidence="", alternative="", affected_step="", authorized=False, addon="factory-runner"):
        return gate.classify(REGISTRY, addon, decision, reason, evidence, alternative, affected_step, authorized)[0]

    def test_generic_no_go(self):
        for reason in gate.GENERIC:
            with self.subTest(reason=reason):
                self.assertEqual(self.check("blocked", reason), "DESVIO_DE_PROCEDIMENTO")
    def test_security(self):
        self.assertEqual(self.check("blocked", "secret_exposed", "token in diff", "sanitize", "publication"), "BLOQUEIO_ESPECIFICO_DOCUMENTADO")
    def test_unproven(self):
        self.assertEqual(self.check("blocked", "error"), "BLOQUEIO_NAO_COMPROVADO")
    def test_waiting_authorization(self):
        self.assertEqual(self.check("prepared"), "PREPARADO_AGUARDANDO_AUTORIZACAO")
    def test_ready_not_pass(self):
        self.assertEqual(self.check("prepared", authorized=True), "PRONTO_PARA_GATES_PERTINENTES")
    def test_unknown(self):
        self.assertEqual(self.check("prepared", addon="missing"), "ERRO_DE_CADASTRO")
