"""Arrival evidence covers early refusals without logging request data."""
import unittest
import test_http as contracts


class WebhookArrival(unittest.TestCase):
    def setUp(self):
        self.fixture=contracts.HTTPContractTests();self.fixture.setUp()
        self.server=contracts.server

    def tearDown(self):self.fixture.tearDown()

    def test_signed_request_records_arrival_before_acceptance(self):
        with self.assertLogs(self.server.LOGGER,level='INFO') as logged:
            self.assertEqual(self.fixture.post_event()[0],200)
        self.assertIn('Meta webhook request: version=0.1.32 exact_path=True length=in_range signature_present=True',logged.output[0])
        self.assertIn('Meta webhook accepted:',logged.output[1])
        text=' '.join(logged.output)
        for private in ('customer-1','business-1','"oi"','test-meta-app-secret','sha256='):
            self.assertNotIn(private,text)

    def test_zero_length_is_observed_even_without_hmac_processing(self):
        with self.assertLogs(self.server.LOGGER,level='INFO') as logged:
            self.assertEqual(self.fixture.request('/webhook/instagram','POST',b'')[0],413)
        self.assertEqual(len(logged.output),1)
        self.assertIn('length=out_of_range signature_present=False',logged.output[0])

    def test_query_route_refusal_is_observed_without_logging_query(self):
        with self.assertLogs(self.server.LOGGER,level='INFO') as logged:
            self.assertEqual(self.fixture.request('/webhook/instagram?secret=PRIVATE_QUERY','POST',b'PRIVATE_BODY',
                {'X-Hub-Signature-256':'PRIVATE_SIGNATURE','Cookie':'PRIVATE_COOKIE'})[0],404)
        text=' '.join(logged.output)
        self.assertIn('exact_path=False',text)
        self.assertNotIn('PRIVATE',text)
        self.assertNotIn('secret=',text)

    def test_unrelated_post_does_not_claim_webhook_arrival(self):
        with self.assertNoLogs(self.server.LOGGER,level='INFO'):
            self.assertEqual(self.fixture.request('/not-webhook','POST',b'PRIVATE')[0],404)
