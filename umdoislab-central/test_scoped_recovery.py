"""Reexecuta a matriz de recuperação existente com conta sintética vinculada."""
import json
import sqlite3
import tempfile
from pathlib import Path
import test_recovery_worker as legacy
from accounts import Account, database_path
class AccountConnection(sqlite3.Connection):
    """Conexão em memória, sem importar/inicializar o servidor."""
    pass


class ScopedRecoveryTests(legacy.WorkerTests):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.account = Account('synthetic_recovery', 'synthetic_recovery', 'Sintética',
                               'business_test', database_path(Path(self.tmp.name), 'synthetic_recovery'), {})
        self.db.commit()
        scoped = sqlite3.connect(':memory:', factory=AccountConnection)
        scoped.account = self.account
        self.db.backup(scoped)
        self.db.close()
        self.db = scoped
        self.item.update(instance=self.account.instance, account_id=self.account.account_id)
        queued = json.loads(self.db.execute('SELECT payload_json FROM n8n_outbox').fetchone()[0])
        queued.update(instance=self.account.instance, account_id=self.account.account_id)
        self.db.execute('UPDATE n8n_outbox SET payload_json=?', (json.dumps(queued),))
        self.db.commit()
        def deliver(item):
            self.assertEqual(item['instance'], self.account.instance)
            self.assertEqual(item['account_id'], self.account.account_id)
            self.sent.append(item['messageId'])
            return 200
        deliver.account = self.account
        self.deliver = deliver

    def tearDown(self):
        super().tearDown()
        self.tmp.cleanup()

    def reader(self, records=None):
        factory = super().reader(records)
        def bound(sender):
            page = factory(sender)
            page.account = self.account
            return page
        bound.account = self.account
        return bound

    def test_wrong_account_reader_blocks_before_claim(self):
        reader = self.reader()
        reader.account = object()
        self.assertEqual(self.run_worker(fetch_pages=reader)['outcome'], 'blocked_configuration')
        self.assertEqual(self.sent, [])

    def test_wrong_account_transport_blocks_before_claim(self):
        def foreign(item):
            self.fail('Transporte de outra conta')
        foreign.account = object()
        self.assertEqual(self.run_worker(transport=foreign)['outcome'], 'blocked_configuration')
        self.assertEqual(self.sent, [])

    def test_no_snapshot_blocks(self):
        def missing(sender): return None
        missing.account = self.account
        self.assertEqual(self.run_worker(fetch_pages=missing)['outcome'], 'blocked_reconciliation')
        self.assertEqual(self.sent, [])
