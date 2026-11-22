"""Operator intent and credential boundaries in the generic client; no network."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('generic_editorial_client',Path(__file__).parents[1]/'tools'/'editorial_client.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)


class GenericClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);(root/'caption.txt').write_text('Selected version')
        (root/'image.png').write_bytes(b'synthetic dry-run bytes')
        self.args=['--format','feed','--caption-file',str(root/'caption.txt'),'--media',str(root/'image.png')]

    def test_default_dry_run_never_constructs_network_client(self):
        with patch.object(client,'Client') as network,contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(client.main(self.args),0)
        network.assert_not_called();self.assertEqual(json.loads(output.getvalue())['networkRequests'],0)

    def test_direct_intent_requires_both_approvals_and_destination_before_network(self):
        for extra in (['--publish-now'],['--approved','--publish-now'],['--publish-approved']):
            with patch.object(client,'Client') as network,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                client.main(self.args+extra)
            network.assert_not_called()

    def test_transfer_only_does_not_call_publish(self):
        with patch.object(client,'Client') as constructor,contextlib.redirect_stdout(io.StringIO()):
            api=constructor.return_value
            api.call.side_effect=[{'found':False},{'id':'a'*32},{'found':True,'id':'b'*32,'importedVersion':1}]
            self.assertEqual(client.main(self.args+['--approved']),0)
        self.assertEqual([call.args[0] for call in api.call.call_args_list],['receipt','upload','commit'])
        self.assertIs(api.call.call_args_list[-1].args[1]['transferApproved'],True)

    def test_retry_uses_receipt_and_original_import_version_without_reupload(self):
        with contextlib.redirect_stdout(io.StringIO()) as dry:client.main(self.args)
        digest=json.loads(dry.getvalue())['requestId'].removeprefix('content_')
        with patch.object(client,'Client') as constructor,contextlib.redirect_stdout(io.StringIO()):
            api=constructor.return_value
            api.call.side_effect=[{'found':True,'status':'draft','version':7,'importedVersion':1,'contentDigest':digest},{'publicationAuthorized':True}]
            client.main(self.args+['--approved','--publish-now','--publish-approved','--instagram-account-id','11111111'])
        calls=api.call.call_args_list
        self.assertEqual([call.args[0] for call in calls],['receipt','publish'])
        self.assertEqual(calls[-1].args[1]['version'],1)

    def test_credentials_require_https_origin_and_redirects_are_refused(self):
        token='cei1.umdoislab.'+'1'*32+'.'+'A'*43
        for origin in ('http://central.example','https://user:secret@central.example','https://central.example/path'):
            with self.assertRaises(ValueError):client.Client(origin,token)
        with self.assertRaises(ValueError):
            client.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')
