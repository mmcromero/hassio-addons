import base64
import json
import threading
import unittest
from http.client import HTTPConnection
from server import make_server, Refused, PROBE, Central

TOKEN = 'cei1.umdoislab.'+'a'*32+'.'+'b'*43
SECOND = 'cei1.secondary.'+'c'*32+'.'+'d'*43
RID = 'test_transfer_0001'

class FakeCentral:
    def __init__(self):
        self.calls = []
        self.records = {}
    def call(self, token, action, data, **kw):
        if token not in (TOKEN, SECOND): raise Refused('denied')
        self.calls.append((token, action, data, kw))
        if action == 'receipt':
            return self.records.get((token, data['requestId']), {'found':False})
        if action == 'upload': return {'id':format(kw['index']+1, '032x')}
        if action == 'commit':
            result = {'found':True,'id':'a'*32,'contentDigest':data['contentDigest'],'status':'draft','published':False}
            self.records[(token,data['requestId'])] = result
            return result
        raise AssertionError(action)

class Contract(unittest.TestCase):
    def setUp(self):
        self.http = make_server('https://central.example',port=0,public_host='editorial.example.ts.net')
        self.fake = self.http.central = FakeCentral()
        self.thread = threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
    def request(self, method='tools/list', args=None, token=TOKEN, headers=None, path='/mcp', verb='POST', notification=False):
        msg = {'jsonrpc':'2.0','method':method,'params':args or {}}
        if not notification: msg['id']=1
        h={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
        if token: h['X-Editorial-Key']=token
        h.update(headers or {})
        c=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            c.request(verb,path,json.dumps(msg),h); resp=c.getresponse(); raw=resp.read()
            return resp.status,json.loads(raw) if raw else None
        finally:c.close()
    def tool(self, name, args=None, **kw):
        return self.request('tools/call',{'name':name,'arguments':args or {}},**kw)
    def manifest(self):
        return {'requestId':RID,'transferApproved':True,'format':'feed','caption':'Teste',
                'media':[{'mime':'image/png','base64':base64.b64encode(b'fake-png-bytes').decode()}]}
    def test_lifecycle_and_tools(self):
        code,body=self.request('initialize',{'protocolVersion':'2025-11-25'}); self.assertEqual(code,200)
        self.assertEqual(body['result']['protocolVersion'],'2025-11-25')
        self.assertEqual(body['result']['serverInfo']['version'],'0.1.5')
        self.assertEqual(self.request('notifications/initialized',notification=True),(202,None))
        code,body=self.request(); self.assertEqual(code,200)
        self.assertEqual([t['name'] for t in body['result']['tools']],['consultar_conexao','consultar_envio','enviar_para_revisao','validar_arquivo_temporario','enviar_arquivo_temporario_para_revisao'])
        self.assertEqual(self.request(verb='GET')[0],405)
        self.assertEqual(self.request(headers={'MCP-Protocol-Version':'2026-07-28'})[0],400)
    def test_no_key_denied(self):
        self.assertEqual(self.request(token=None)[0],403)
        self.assertEqual(self.request(token=TOKEN[:-1]+'z')[0],403)
        self.assertEqual(self.fake.calls,[])
    def test_origin_host_path(self):
        self.assertEqual(self.request(headers={'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request(headers={'Host':'evil.test'})[0],403)
        self.assertEqual(self.request(path='/mcp?key=secret')[0],404)
        self.assertEqual(self.request(headers={'Host':'editorial.example.ts.net','Origin':'https://editorial.example.ts.net'})[0],200)
    def test_transfer_and_idempotence(self):
        data=self.manifest(); code,body=self.tool('enviar_para_revisao',data); self.assertEqual(code,200)
        self.assertNotIn('isError',body['result']); self.assertEqual(json.loads(body['result']['content'][0]['text'])['status'],'draft')
        self.tool('enviar_para_revisao',data)
        self.assertEqual(sum(a=='upload' for _,a,_,_ in self.fake.calls),1)
        self.assertEqual(sum(a=='commit' for _,a,_,_ in self.fake.calls),1)
        data['caption']='changed'; _,body=self.tool('enviar_para_revisao',data); self.assertTrue(body['result']['isError'])
    def test_no_approval_or_invented_url(self):
        data=self.manifest(); data['transferApproved']=False
        self.assertTrue(self.tool('enviar_para_revisao',data)[1]['result']['isError'])
        data=self.manifest(); data['media'][0]={'mime':'image/png','url':'https://evil.test'}
        self.assertTrue(self.tool('enviar_para_revisao',data)[1]['result']['isError'])
        self.assertTrue(all(a=='receipt' for _,a,_,_ in self.fake.calls))
    def test_account_isolation(self):
        self.tool('enviar_para_revisao',self.manifest())
        result=self.tool('consultar_envio',{'requestId':RID},token=SECOND)[1]['result']['content'][0]['text']
        self.assertFalse(json.loads(result)['found'])
        result=self.tool('consultar_conexao',token=SECOND)[1]['result']['content'][0]['text']
        self.assertEqual(json.loads(result)['account'],'secondary')
    def test_no_publish(self):
        self.assertTrue(self.tool('import_publish',{})[1]['result']['isError'])
        with self.assertRaises(Refused): Central('https://central.example').call(TOKEN,'publish',{})
        self.assertTrue(all(a=='receipt' for _,a,_,_ in self.fake.calls))
    def test_invalid_base64_and_format(self):
        data=self.manifest(); data['media'][0]['base64']='not base64'
        self.assertTrue(self.tool('enviar_para_revisao',data)[1]['result']['isError'])
        data=self.manifest(); data['format']='carousel'
        self.assertTrue(self.tool('enviar_para_revisao',data)[1]['result']['isError'])
    def test_upstream_error_sanitized(self):
        data=self.manifest(); self.fake.records[(TOKEN,RID)]={'found':True,'status':'deleted','contentDigest':'bad'}
        self.assertTrue(self.tool('enviar_para_revisao',data)[1]['result']['isError'])
        with self.assertRaises(ValueError): Central('https://central.example/path')

if __name__=='__main__': unittest.main()
