"""Multi-account contract over local HTTP, fake Central, no real service."""
import hashlib
import json
import threading
import unittest
import server
import test_server as legacy

KEY='cei2.'+'c'*32+'.'+'d'*43
RID='multi_test_request_001'
ITEM={'fileId':'synthetic_file_001','mime':'image/png','bytes':25,'sha256':'a'*64}


class MultiCentral:
    def __init__(self):
        self.calls,self.receipts=[],{}
    def call(self,token,action,data,**kw):
        if token!=KEY:raise server.Refused('denied')
        self.calls.append((action,data,kw))
        if action=='accounts':return {'accounts':[{'id':'umdoislab'},{'id':'secondary'}],'publishingAvailable':False}
        if action=='resolve':
            account={'umdoislab':'umdoislab','Tudo é 3D':'secondary','secondary':'secondary'}.get(data.get('destination'))
            if not account:raise server.Refused('ambiguous')
            return {'connected':True,'account':account,'publishingAvailable':False}
        account=kw.get('account')
        if account not in ('umdoislab','secondary'):raise server.Refused('missing account')
        if action=='receipt':return self.receipts.get((account,data['requestId']),{'found':False})
        if action=='drive_validate':return {'verified':True,'persisted':False,'mime':data['mime'],'bytes':data['bytes'],'sha256':data['sha256']}
        if action=='drive_stage':return {'id':format(data['index']+1,'032x')}
        if action=='upload':return {'id':format(kw['index']+1,'032x')}
        if action=='commit':
            result={'found':True,'id':hashlib.sha256((account+data['requestId']).encode()).hexdigest()[:32],
                    'contentDigest':data['contentDigest'],'status':'draft','published':False,'publicationAuthorized':False}
            self.receipts[(account,data['requestId'])]=result
            return result
        raise AssertionError(action)


class MultiContract(unittest.TestCase):
    request=legacy.Contract.request
    stop=legacy.Contract.stop
    def setUp(self):
        self.http=server.make_server('https://central.example',port=0,public_host='editorial.example.ts.net')
        self.fake=self.http.central=MultiCentral()
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def tool(self,name,args=None):
        status,body=self.request('tools/call',{'name':name,'arguments':args or {}},token=KEY)
        self.assertEqual(status,200)
        return body['result']
    def payload(self,account='Tudo é 3D'):
        out={'requestId':RID,'transferApproved':True,'format':'story','caption':'Synthetic','media':[ITEM]}
        if account is not None:out['conta']=account
        return out
    def test_schema_and_forgery(self):
        status,body=self.request(token=KEY)
        self.assertEqual(status,200)
        names={t['name'] for t in body['result']['tools']}
        self.assertTrue({'listar_contas','validar_arquivo_drive','enviar_arquivo_drive_para_revisao'}<=names)
        self.assertEqual(len(json.loads(self.tool('listar_contas')['content'][0]['text'])['accounts']),2)
        self.assertEqual(self.request(token=KEY[:-1]+'e')[0],403)
    def test_ambiguous_or_missing_approval(self):
        for payload in [self.payload(None),self.payload('unknown'),{**self.payload(),'transferApproved':False}]:
            self.assertTrue(self.tool('enviar_arquivo_drive_para_revisao',payload)['isError'])
        self.assertFalse(any(a in ('drive_stage','upload','commit') for a,_,_ in self.fake.calls))
    def test_retry_and_account_binding(self):
        first=json.loads(self.tool('enviar_arquivo_drive_para_revisao',self.payload())['content'][0]['text'])
        self.assertEqual(first['account'],'secondary')
        self.assertEqual(first['status'],'draft')
        self.assertFalse(first['published'])
        second=json.loads(self.tool('enviar_arquivo_drive_para_revisao',self.payload())['content'][0]['text'])
        self.assertEqual(first,second)
        self.assertEqual(sum(a=='drive_stage' for a,_,_ in self.fake.calls),1)
        other=json.loads(self.tool('enviar_arquivo_drive_para_revisao',self.payload('umdoislab'))['content'][0]['text'])
        self.assertNotEqual(other['id'],first['id'])
        for action,_,kw in self.fake.calls:
            if action in ('drive_stage','receipt','commit'):self.assertIn(kw.get('account'),('secondary','umdoislab'))
    def test_read_only(self):
        data=json.loads(self.tool('validar_arquivo_drive',{**ITEM,'conta':'umdoislab'})['content'][0]['text'])
        self.assertTrue(data['verified'])
        self.assertFalse(data['persisted'])
        self.assertFalse(any(a in ('drive_stage','upload','commit') for a,_,_ in self.fake.calls))


if __name__=='__main__':unittest.main()
