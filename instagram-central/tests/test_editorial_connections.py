import tempfile
import unittest
from pathlib import Path
from editorial_connections import Connections, Denied, resolve


def account(bid, name, username, aliases=()):
    return dict(business_id=bid, display_name=name, username=username,
                instagram_account_id='123', enabled=True, aliases=aliases)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 1000
        self.accounts = [account('umdoislab', 'Umdoislab', 'umdoislab', ['1-2 Lab']),
                         account('tudoe3d', 'Tudo é 3D', 'tudoe3d')]
        self.store = Connections(Path(self.tmp.name)/'test.sqlite', lambda: self.accounts, lambda: self.now)

    def test_owner_future_accounts(self):
        token = self.store.create('Claude', 'owner_all', [])['token']
        with self.store.authorize(token) as (_, a):
            self.assertEqual(resolve(a, '1-2 Lab'), 'umdoislab')
            self.assertEqual(resolve(a, 'Tudo e 3D'), 'tudoe3d')
            with self.assertRaises(Denied): resolve(a)
        self.accounts.append(account('newprofile', 'Novo', 'novo'))
        with self.store.authorize(token) as (_, a):
            self.assertEqual(resolve(a, '@novo'), 'newprofile')

    def test_delegate_no_future_access(self):
        token = self.store.create('Delegada', 'selected', ['tudoe3d'])['token']
        self.accounts.append(account('newprofile', 'Novo', 'novo'))
        with self.store.authorize(token) as (_, a):
            self.assertEqual(resolve(a), 'tudoe3d')
            for target in ['umdoislab', 'newprofile', 'inexistente']:
                with self.assertRaises(Denied): resolve(a, target)
        self.accounts[1]['enabled'] = False
        with self.store.authorize(token) as (_, a):
            self.assertEqual(a, [])
            with self.assertRaises(Denied): resolve(a)

    def test_expiry_revocation_and_forgery(self):
        k = self.store.create('Claude', 'owner_all', [])
        for token in ['cei1.umdoislab.abc.def', k['token'][:-1] + ('a' if k['token'][-1] != 'a' else 'b')]:
            with self.assertRaises(Denied), self.store.authorize(token): pass
        self.assertTrue(self.store.revoke(k['id']))
        with self.assertRaises(Denied), self.store.authorize(k['token']): pass
        k = self.store.create('Another', 'owner_all', [])
        self.now = k['expires']
        with self.assertRaises(Denied), self.store.authorize(k['token']): pass

    def test_ambiguous_and_invalid_grants(self):
        for scope, grants in [('selected', []), ('selected', ['unknown']), ('owner_all', ['umdoislab']), ('bad', [])]:
            with self.assertRaises(Denied): self.store.create('x', scope, grants)
        self.accounts[1]['aliases'] = ['1-2 Lab']
        token = self.store.create('Claude', 'owner_all', [])['token']
        with self.store.authorize(token) as (_, a):
            with self.assertRaises(Denied): resolve(a, '1-2 Lab')
            self.assertEqual(resolve(a, 'umdoislab'), 'umdoislab')

    def test_delegate_permissions_change_without_new_token(self):
        key = self.store.create('Delegate', 'selected', ['tudoe3d'])
        self.accounts.append(account('newprofile', 'Novo', 'novo'))
        self.store.update_grants(key['id'], ['newprofile'])
        with self.store.authorize(key['token']) as (_, allowed):
            self.assertEqual(resolve(allowed), 'newprofile')
            with self.assertRaises(Denied): resolve(allowed, 'tudoe3d')
        with self.assertRaises(Denied): self.store.update_grants(key['id'], ['unknown'])
        owner = self.store.create('Owner', 'owner_all', [])
        with self.assertRaises(Denied): self.store.update_grants(owner['id'], ['newprofile'])

    def test_management_does_not_disclose_secrets(self):
        k = self.store.create('Claude', 'owner_all', [])
        row = self.store.list()[0]
        self.assertEqual(row['id'], k['id'])
        self.assertNotIn('digest', row)
        self.assertNotIn('token', row)


if __name__ == '__main__': unittest.main()
