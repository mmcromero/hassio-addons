import hashlib
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from stage2_bridge import handle, PREFIX, revoke


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          CREATE TABLE inbound_ids(sender_id TEXT,message_id TEXT,PRIMARY KEY(sender_id,message_id));
          CREATE TABLE conversation_turns(sender_id TEXT,message_id TEXT,role TEXT,text TEXT);
          CREATE TABLE replies(request_id TEXT PRIMARY KEY);
          CREATE TABLE conversations(sender_id TEXT PRIMARY KEY,sender_name TEXT,subject TEXT,summary TEXT,
            last_message TEXT,last_message_id TEXT,status TEXT,updated_at TEXT,created_at TEXT,choice_state TEXT,
            choice_message_id TEXT,last_bot_text TEXT,bot_repeat_count INTEGER,fallback_count INTEGER);
        ''')
        self.account = SimpleNamespace(instance='umdoislab', lock=threading.RLock())
        self.sender = 'synthetic-contact'
        self.mode = 'tests'
        self.eligible = True
        self.bridge_ok = True
        self.human = False
        self.sends = 0
        self.ref = None
        self.next_action = "auto"
        self.ev = dict(instance='umdoislab', senderId=self.sender, messageId='msg1', messageText='Produto?')

    def tearDown(self):
        self.db.close()

    def request(self, op, **changes):
        h = SimpleNamespace(account=self.account, path=PREFIX+op, bridge=lambda: self.bridge_ok,
                            respond=lambda status, body: (status, body), send_automated=self.send)
        payload = dict(self.ev, admissionRef=self.ref, **{k:v for k,v in changes.items() if k != 'admissionRef'})
        if 'admissionRef' in changes:
            payload['admissionRef'] = changes['admissionRef']
        result = handle(h, payload, connect=lambda account: self.db,
                      get_policy=lambda db: {'mode':self.mode}, contact_policy=self.policy,
                      valid_event=lambda ev, account: ev.get('instance') == account.instance,
                      valid_sender=lambda s: s.startswith('synthetic-'), process_inbound=self.inbound,
                      routing_decision=self.route, now=lambda:'2026-11-24T22:00:00+00:00')
        if op == 'inbound' and 'admissionRef' in result[1]:
            self.ref = result[1]['admissionRef']
        return result

    def policy(self, db, sender):
        allowed = self.eligible and sender == self.sender
        return dict(allowed=allowed,reason='test' if allowed else 'excluded')

    def inbound(self, ev, account):
        with self.db:
            if self.db.execute('SELECT 1 FROM inbound_ids WHERE sender_id=? AND message_id=?', (ev['senderId'],ev['messageId'])).fetchone():
                return {'action':'ignore'}
            self.db.execute('INSERT INTO inbound_ids VALUES(?,?)',(ev['senderId'],ev['messageId']))
            self.db.execute('INSERT INTO conversation_turns VALUES(?,?,?,?)',(ev['senderId'],ev['messageId'],'client',ev['messageText']))
        return {'action':self.next_action}

    def route(self, instance, sender, account):
        row=self.db.execute('SELECT status,choice_state FROM conversations WHERE sender_id=?',(sender,)).fetchone()
        return {'allowAutoReply':not self.human and (row is None or row['status']=='done' or row['choice_state']=='opted_in')}

    def send(self, data):
        self.sends += 1
        key='auto-'+hashlib.sha256((data['senderId']+'|'+data['messageId']+'|'+data['kind']).encode()).hexdigest()
        with self.db:
            self.db.execute('INSERT INTO replies VALUES(?)',(key,))
        return 200, {'ok':True,'delivery':'accepted_not_confirmed','kind':data['kind']}

    def count(self, table):
        return self.db.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def test_test_mode_and_duplicate(self):
        for mode in ('all','new'):
            self.mode=mode
            status, result=self.request('inbound')
            self.assertEqual((status,result['action'],result['testSendAuthorized']),(200,'ignore',False))
        self.assertEqual(self.count('inbound_ids'),0)
        self.mode='tests'
        self.assertEqual(self.request('inbound')[1]['action'],'auto')
        self.assertEqual(self.request('inbound')[1]['action'],'ignore')
        self.assertEqual(self.count('inbound_ids'),1)
        self.assertEqual(self.count('conversation_turns'),1)

    def test_auth_account_and_policy(self):
        self.bridge_ok=False
        self.assertEqual(self.request('inbound')[0],403)
        self.bridge_ok=True
        self.assertEqual(self.request('inbound',instance='other')[0],422)
        self.eligible=False
        self.assertEqual(self.request('inbound')[1]['action'],'ignore')
        self.assertEqual(self.count('inbound_ids'),0)

    def test_context_isolation_and_stale(self):
        self.assertEqual(self.request('context')[0],409)
        self.request('inbound')
        with self.db:
            self.db.execute('INSERT INTO conversation_turns VALUES(?,?,?,?)',('synthetic-other','other','client','foreign'))
        result=self.request('context')[1]
        self.assertEqual(result['turns'],[{'role':'client','text':'Produto?'}])
        self.assertEqual(result['authorization']['mode'],'tests')
        self.request('inbound',messageId='msg2')
        self.assertEqual(self.request('context')[0],409)
        self.assertEqual(self.request('send-auto',kind='normal')[0],409)

    def test_handoff_original_and_no_duplicate(self):
        self.request('inbound')
        self.assertEqual(self.request('handoff',reason='unknown')[0],422)
        self.assertEqual(self.request('handoff',reason={})[0],422)
        status, result=self.request('handoff',reason='model_error')
        self.assertEqual((status,result['recorded'],result['messageId']),(200,True,'msg1'))
        self.assertEqual(self.count('inbound_ids'),1)
        self.assertEqual(self.count('conversation_turns'),1)
        row=self.db.execute('SELECT * FROM conversations').fetchone()
        self.assertEqual((row['status'],row['last_message_id'],row['last_message']),('pending','msg1','Produto?'))
        self.assertEqual(self.request('handoff',reason='model_error')[0],409)
        self.assertEqual(self.request('send-auto',kind='handoff')[0],200)
        self.assertEqual(self.request('send-auto',kind='normal')[0],409)
        self.assertEqual(self.sends,1)

    def test_legacy_inbound_cannot_obtain_admission(self):
        self.inbound(self.ev, self.account)
        self.assertEqual(self.request('inbound')[1]['action'],'ignore')
        self.assertIsNone(self.ref)
        self.assertEqual(self.request('context')[0],409)
        self.assertEqual(self.request('send-auto',kind='normal')[0],409)
        self.assertEqual(self.sends,0)

    def test_revoked_expired_and_mismatched_admissions(self):
        self.request('inbound')
        original = self.ref
        self.assertEqual(self.request('context',admissionRef='x'*43)[0],409)
        with self.db:
            self.db.execute('UPDATE stage2_admissions SET expires_at=0')
        self.assertEqual(self.request('context')[0],409)
        self.request('inbound',messageId='msg2')
        self.assertEqual(self.request('context',messageId='msg2',admissionRef=original)[0],409)
        with self.db:
            revoke(self.db,self.sender)
        self.assertEqual(self.request('send-auto',messageId='msg2',kind='normal')[0],409)
        self.assertEqual(self.sends,0)

    def test_silent_and_kind_binding(self):
        self.next_action='silent'
        self.assertEqual(self.request('inbound')[1]['action'],'silent')
        self.assertIsNone(self.ref)
        self.assertEqual(self.request('send-auto',kind='normal')[0],409)
        self.next_action='auto'
        self.request('inbound',messageId='msg2')
        self.assertEqual(self.request('send-auto',messageId='msg2',kind='handoff')[0],409)
        self.assertEqual(self.request('send-auto',messageId='msg2',kind='choice')[0],409)
        self.assertEqual(self.sends,0)

    def test_uncertain_transport_consumes_admission(self):
        self.request('inbound')
        self.send=lambda data:(502,{'error':'uncertain'})
        self.assertEqual(self.request('send-auto',kind='normal')[0],502)
        self.assertEqual(self.request('send-auto',kind='normal')[0],409)

    def test_recheck_and_offer(self):
        self.request('inbound')
        self.human=True
        self.assertEqual(self.request('context')[0],409)
        self.assertEqual(self.request('handoff',reason='model_error')[0],409)
        self.human=False
        self.mode='all'
        self.assertEqual(self.request('send-auto',kind='normal')[0],403)
        self.mode='tests'
        self.assertEqual(self.request('send-auto',kind='unknown')[0],422)
        self.assertEqual(self.request('send-auto',kind='human_offer')[0],200)
        self.assertEqual(self.request('send-auto',kind='human_offer')[0],409)
        self.assertEqual(self.sends,1)


if __name__=='__main__':
    unittest.main()
