"""M002: prova autenticada PN/LID, respostas simuladas, nenhuma rede real."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from accounts import Account
from outgoing_verification import verify_outgoing
from test_outgoing_verification import MID, SENDER, Response, payload, record

LID = '123456789012345@lid'


def lid_record(**changes):
    result = record(**changes)
    result['key'].update(remoteJid=LID, remoteJidAlt=SENDER)
    return result


class PNLIDVerificationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.no_network = patch('socket.create_connection', side_effect=AssertionError('Rede real proibida'))
        self.no_network.start()

    def tearDown(self):
        self.no_network.stop()

    def verify(self, primary, alternate=None, **changes):
        def opener(request, timeout):
            body = json.loads(request.data)
            self.calls.append(body)
            self.assertEqual(request.full_url, 'http://evolution.invalid/chat/findMessages/umdoislab')
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.get_header('Apikey'), 'synthetic-key')
            self.assertEqual(body['where']['key']['id'], MID)
            self.assertEqual((body['page'], body['offset']), (1, 10))
            field = 'remoteJid' if len(self.calls) == 1 else 'remoteJidAlt'
            self.assertEqual(body['where']['key'], {field: SENDER, 'id': MID})
            value = primary if field == 'remoteJid' else alternate
            if isinstance(value, Exception):
                raise value
            return Response(value)
        args = dict(base_url='http://evolution.invalid', instance='umdoislab',
                    api_key='synthetic-key', opener=opener)
        args.update(changes)
        return verify_outgoing(SENDER, MID, **args)

    def test_pn_positive_does_not_query_alternative(self):
        self.assertTrue(self.verify(payload([record()])))
        self.assertEqual(len(self.calls), 1)

    def test_empty_pn_and_valid_lid(self):
        self.assertTrue(self.verify(payload([]), payload([lid_record()])))
        self.assertEqual(len(self.calls), 2)

    def test_empty_pn_with_zero_pages_allows_lid(self):
        empty = payload([])
        empty['messages']['pages'] = 0
        self.assertTrue(self.verify(empty, payload([lid_record()])))

    def test_both_partitions_empty_reject(self):
        self.assertFalse(self.verify(payload([]), payload([])))
        self.assertEqual(len(self.calls), 2)

    def test_unrelated_or_unresolved_jid_rejects(self):
        for remote in ('5511888888888@s.whatsapp.net', SENDER, 'status@broadcast',
                       '12345@g.us', 'x@lid', '1234@lid', '1'*26+'@lid', None):
            with self.subTest(remote=remote):
                self.calls.clear()
                r = lid_record()
                r['key']['remoteJid'] = remote
                self.assertFalse(self.verify(payload([]), payload([r])))

    def test_lid_requires_exact_alt_pn(self):
        for alt in (None, '5511888888888@s.whatsapp.net', LID, SENDER.upper()):
            with self.subTest(alt=alt):
                self.calls.clear()
                r = lid_record()
                r['key']['remoteJidAlt'] = alt
                self.assertFalse(self.verify(payload([]), payload([r])))

    def test_alternative_exact_id_and_boolean_direction_required(self):
        for changes in ({'mid': 'different'}, {'from_me': False}, {'from_me': 'true'},
                        {'from_me': 1}, {'timestamp': None}, {'timestamp': True},
                        {'timestamp': 1}, {'timestamp': '1795154160'}):
            with self.subTest(changes=changes):
                self.calls.clear()
                self.assertFalse(self.verify(payload([]), payload([lid_record(**changes)])))

    def test_identical_sql_duplicates_accepted_for_lid(self):
        self.assertTrue(self.verify(payload([]), payload([lid_record(row_id=1), lid_record(row_id=2)])))

    def test_conflicting_lid_duplicates_rejected(self):
        for changes in ({'message': 'diferente'}, {'from_me': False}, {'timestamp': 1795154161}):
            with self.subTest(changes=changes):
                self.calls.clear()
                self.assertFalse(self.verify(payload([]), payload([lid_record(), lid_record(row_id=2, **changes)])))

    def test_two_lids_claiming_same_id_and_pn_are_conflicting(self):
        a, b = lid_record(), lid_record(row_id=2)
        b['key']['remoteJid'] = '987654321098765@lid'
        self.assertFalse(self.verify(payload([]), payload([a, b])))

    def test_invalid_primary_never_falls_back_to_valid_lid(self):
        cases = [None, {}, [], {'messages': {}}, payload([record(mid='other')]),
                 payload([record(from_me=False)]), payload([record(sender='5511888888888@s.whatsapp.net')])]
        for value in cases:
            with self.subTest(value=value):
                self.calls.clear()
                self.assertFalse(self.verify(value, payload([lid_record()])))
                self.assertEqual(len(self.calls), 1)

    def test_conflicting_primary_not_hidden_by_alternative(self):
        for changes in ({'message': 'outro'}, {'from_me': False}, {'timestamp': 1795154161}):
            with self.subTest(changes=changes):
                self.calls.clear()
                self.assertFalse(self.verify(payload([record(), record(row_id=2, **changes)]), payload([lid_record()])))
                self.assertEqual(len(self.calls), 1)

    def test_partial_or_invalid_pagination_rejects_both_partitions(self):
        cases = [({'total': 2}, [record()]), ({'pages': 2}, []),
                 ({'currentPage': 2}, []), ({'total': True}, []),
                 ({'pages': '1'}, []), ({'currentPage': True}, []),
                 ({'pages': 0}, [record()]), ({'total': -1}, []),
                 ({'total': 11}, [record()]*11), ({'records': None}, [])]
        for meta, records in cases:
            for partition in ('pn', 'lid'):
                with self.subTest(meta=meta, partition=partition):
                    self.calls.clear()
                    bad = payload(records)
                    bad['messages'].update(meta)
                    if partition == 'pn':
                        self.assertFalse(self.verify(bad, payload([lid_record()])))
                        self.assertEqual(len(self.calls), 1)
                    else:
                        self.assertFalse(self.verify(payload([]), bad))

    def test_401_and_timeout_fail_closed_on_either_query(self):
        for failure in (HTTPError('http://evolution.invalid', 401, 'Não autorizado', {}, None), TimeoutError()):
            for partition in ('pn', 'lid'):
                with self.subTest(failure=type(failure).__name__, partition=partition):
                    self.calls.clear()
                    primary, alternate = (failure, payload([lid_record()])) if partition == 'pn' else (payload([]), failure)
                    self.assertFalse(self.verify(primary, alternate))
                    self.assertEqual(len(self.calls), 1 if partition == 'pn' else 2)

    def test_http_non_success_and_malformed_json_reject(self):
        for status, raw in ((401, b'{}'), (500, b'{}'), (200, b''), (200, b'{'),
                            (200, b'\xff'), (200, b'x'*2_000_001)):
            for partition in ('pn', 'lid'):
                with self.subTest(status=status, raw_length=len(raw), partition=partition):
                    responses = []
                    if partition == 'lid':
                        responses.append(Response(payload([])))
                    response = Response({})
                    response.status = status
                    response.data = raw
                    responses.append(response)
                    with patch('outgoing_verification.urlopen', side_effect=responses) as opener:
                        self.assertFalse(verify_outgoing(SENDER, MID, base_url='http://evolution.invalid',
                                                        instance='umdoislab', api_key='synthetic-key'))
                        self.assertEqual(opener.call_count, 1 if partition == 'pn' else 2)

    def test_malformed_records_reject_both_partitions(self):
        for malformed in (None, [], {'key': None}, {'key': {}}, {'key': 'x'}):
            for partition in ('pn', 'lid'):
                with self.subTest(malformed=malformed, partition=partition):
                    self.calls.clear()
                    bad = payload([malformed])
                    self.assertFalse(self.verify(bad if partition == 'pn' else payload([]), bad))

    def test_missing_or_foreign_credentials_never_query(self):
        account = Account('synthetic', 'umdoislab', 'Teste', 'business_test', Path('/unused'), {
            'evolution_url': 'http://evolution.invalid', 'evolution_api_key': 'synthetic-key'})
        for changes in ({'api_key': ''}, {'api_key': 'foreign', 'account': account},
                        {'instance': 'foreign', 'account': account},
                        {'base_url': 'http://foreign.invalid', 'account': account},
                        {'account': replace(account, enabled=False)},
                        {'account': replace(account, instance='foreign', config={})}):
            with self.subTest(changes=tuple(changes)):
                self.calls.clear()
                self.assertFalse(self.verify(payload([]), payload([lid_record()]), **changes))
                self.assertEqual(self.calls, [])

    def test_valid_account_allows_authenticated_lid_fallback(self):
        account = Account('synthetic', 'umdoislab', 'Teste', 'business_test', Path('/unused'), {
            'evolution_url': 'http://evolution.invalid', 'evolution_api_key': 'synthetic-key'})
        self.assertTrue(self.verify(payload([]), payload([lid_record()]), account=account))
