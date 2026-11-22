"""Sender profile HTTP and Graph transport contracts; loopback and mocks only."""
import io
import json
import unittest
from urllib.parse import urlencode
from unittest.mock import patch
from PIL import Image
import test_http as contracts
import instagram_connection as meta

server=contracts.server


class SenderProfileHTTP(unittest.TestCase):
    def setUp(self):
        self.fixture=contracts.HTTPContractTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.config.update({'instagram_account_id':'11111111','meta_graph_version':'v27.0'})
        self.credential={'business_id':'umdoislab','account_id':'11111111','username':'umdoislab',
                         'verified_at':1,'access_token':'synthetic-token-only-123456'}
        raw=json.dumps({'object':'instagram','entry':[{'id':'11111111','messaging':[{
            'sender':{'id':'99999999'},'recipient':{'id':'11111111'},
            'message':{'mid':'test-only','text':'mensagem preservada'}}]}]}).encode()
        self.assertEqual(server.persist(raw,'11111111'),1)
        _,headers,_=self.fixture.request('/auth/login','POST',urlencode({
            'username':'admin','password':self.fixture.config['panel_password']}),
            {'Content-Type':'application/x-www-form-urlencoded'})
        self.headers={'Cookie':headers['Set-Cookie'].split(';')[0]}

    def test_profile_routes_require_session_and_restrict_known_sender(self):
        path='/panel?view=sender-profile&sender=99999999'
        image_path='/panel?view=sender-image&sender=99999999'
        photo=io.BytesIO()
        Image.new('RGB',(96,96),'blue').save(photo,'JPEG')
        with patch.object(server,'_meta_credential',return_value=self.credential), \
             patch.object(meta,'request_graph',return_value={'name':'Nome Teste','username':'teste',
                          'profile_pic':'https://scontent.cdninstagram.com/photo.jpg'}) as graph, \
             patch.object(server.account_avatar,'download',return_value=photo.getvalue()) as download:
            self.assertEqual(self.fixture.request(path)[0],403)
            self.assertEqual(self.fixture.request(image_path)[0],403)
            self.assertEqual(self.fixture.request('/panel?view=sender-profile&sender=77777777',headers=self.headers)[0],404)
            status,_,markup=self.fixture.request('/panel?utm_source=chatgpt.com',headers=self.headers)
            self.assertEqual(status,200)
            self.assertIn(b'mensagem preservada',markup)
            self.assertIn(b'data-sender-profile=',markup)
            graph.assert_not_called()
            status,_,raw=self.fixture.request(path,headers=self.headers)
            self.assertEqual(status,200)
            self.assertEqual(json.loads(raw),{'name':'Nome Teste','username':'teste','has_photo':True,'status':'confirmed'})
            status,headers,raw=self.fixture.request(image_path,headers=self.headers)
            self.assertEqual(status,200)
            self.assertEqual(headers['Content-Type'],'image/jpeg')
            self.assertEqual(headers['Cross-Origin-Resource-Policy'],'same-origin')
            self.assertEqual(raw,photo.getvalue())
            graph.assert_called_once()
            download.assert_called_once()
        with server.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],1)

    def test_graph_profile_fields_allowed_only_on_numeric_get(self):
        token=self.credential['access_token']
        requests=[]
        def open_mock(req,timeout):
            requests.append(req)
            return io.BytesIO(b'{"name":"Teste"}')
        fields={'fields':'name,username,profile_pic'}
        result=meta.request_graph('v27.0','/99999999',token,fields=fields,opener=open_mock)
        self.assertEqual(result,{'name':'Teste'})
        self.assertEqual(requests[0].get_method(),'GET')
        self.assertNotIn(token,requests[0].full_url)
        self.assertEqual(requests[0].get_header('Authorization'),'Bearer '+token)
        for path,method,query in [('/99999999','POST',fields),('/other','GET',fields),
                                   ('/99999999','GET',{'fields':'name,email'})]:
            with self.assertRaises(meta.ConnectionError):
                meta.request_graph('v27.0',path,token,method=method,fields=query,opener=open_mock)
        self.assertEqual(len(requests),1)
