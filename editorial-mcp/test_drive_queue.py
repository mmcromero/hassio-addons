import copy
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from drive_queue import Queue, parse_order, Reject, Drive, TOKEN_URL, SCOPE

ROOT='root_1234567890'
FOLDER='folder_1234567890'
FILE='order_1234567890'
MEDIA='media_1234567890'
ACCOUNT='tudoe3d'
OWNER='owner@example.invalid'
READER='read@project.iam.gserviceaccount.com'
KEY='cei2.'+'a'*32+'.'+'b'*43
REQUEST="driveq_"+"c"*32
MANIFEST={'schemaVersion':1,'conta':ACCOUNT,'requestId':REQUEST,'transferApproved':True,'format':'feed','caption':'TESTE NÃO PUBLICAR','media':[{'fileId':MEDIA,'mime':'image/png','bytes':12,'sha256':'a'*64}]}

class FakeDrive:
    email=READER
    def __init__(self):
        self.raw=json.dumps(MANIFEST).encode()
        created=datetime.now(timezone.utc).isoformat()
        self.data={}
        for id_, parent, name, mime, size in [(ROOT,None,'root','application/vnd.google-apps.folder',0),(FOLDER,ROOT,ACCOUNT,'application/vnd.google-apps.folder',0),(FILE,FOLDER,'ordem-'+REQUEST+'.json','application/json',len(self.raw)),(MEDIA,FOLDER,'image.png','image/png',12)]:
            self.data[id_]={'id':id_,'name':name,'mimeType':mime,'parents':[parent] if parent else [],'trashed':False,'owners':[{'emailAddress':OWNER}],'size':str(size),'version':'1','createdTime':created}
        self.extra={}
    def metadata(self,id_): return copy.deepcopy(self.data[id_])
    def permissions(self,id_): return [{'type':'user','role':'owner','emailAddress':OWNER},{'type':'user','role':'reader','emailAddress':READER}]+self.extra.get(id_,[])
    def children(self,id_): return [copy.deepcopy(x) for x in self.data.values() if x['parents']==[id_]]
    def content(self,id_): return self.raw
    def set_manifest(self,manifest):
        self.raw=json.dumps(manifest).encode(); self.data[FILE]['size']=str(len(self.raw))

class TestQueue(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.drive=FakeDrive(); self.calls=[]; self.fail=False; self.receipt=None
        self.path=Path(self.tmp.name)/'queue.sqlite'
        self.config={'root_id':ROOT,'owner_email':OWNER,'central_key':KEY,'accounts':[ACCOUNT]}
        self.queue=Queue(self.drive,None,self.call,self.config,self.path)
    def tearDown(self):
        self.queue.close(); self.tmp.cleanup()
    def call(self,central,key,method,args):
        self.assertEqual(key,KEY); self.assertEqual(args['conta'],ACCOUNT); self.calls.append((method,args['requestId']))
        if method=='enviar_arquivo_drive_para_revisao':
            self.receipt={'found':True,'id':'a'*32,'status':'draft','published':False,'publicationAuthorized':False,'account':ACCOUNT}
            if self.fail: raise OSError('lost response')
        return self.receipt.copy()
    def state(self): return self.queue.db.execute('SELECT state FROM orders WHERE id=?',(FILE,)).fetchone()
    def test_success_and_restart(self):
        self.queue.poll(); self.assertEqual(self.state(),('done',)); self.assertEqual(len(self.calls),2)
        self.queue.close(); self.queue=Queue(self.drive,None,self.call,self.config,self.path); self.queue.poll(); self.assertEqual(len(self.calls),2)
    def test_lost_response_same_id(self):
        self.fail=True; self.queue.poll(); self.assertEqual(self.state(),('retry',)); self.fail=False
        self.queue.db.execute('UPDATE orders SET retry_after=0'); self.queue.db.commit(); self.queue.poll(); self.assertEqual(self.state(),('done',)); self.assertEqual(len({x[1] for x in self.calls}),1)
    def test_public_root(self):
        self.drive.extra[ROOT]=[{'type':'anyone','role':'reader'}]
        with self.assertRaises(Reject): self.queue.poll()
        self.assertFalse(self.calls)
    def test_untrusted_writer(self):
        self.drive.extra[FILE]=[{'type':'user','role':'writer','emailAddress':'other@example.invalid'}]
        self.queue.poll(); self.assertEqual(self.state(),('rejected',));self.assertFalse(self.calls)
    def test_other_account(self):
        self.drive.set_manifest({**MANIFEST,'conta':'other'});self.queue.poll();self.assertEqual(self.state(),('rejected',));self.assertFalse(self.calls)
    def test_media_outside_folder(self):
        self.drive.data[MEDIA]['parents']=[ROOT];self.queue.poll();self.assertEqual(self.state(),('rejected',));self.assertFalse(self.calls)
    def test_expired(self):
        self.drive.data[FILE]['createdTime']='2020-01-01T00:00:00Z';self.queue.poll();self.assertEqual(self.state(),('rejected',));self.assertFalse(self.calls)
    def test_no_approval(self):
        self.drive.set_manifest({**MANIFEST,'transferApproved':False});self.queue.poll();self.assertEqual(self.state(),('rejected',));self.assertFalse(self.calls)
    def test_manifest_changed(self):
        with patch.object(self.drive,'metadata',side_effect=lambda id_: {**self.drive.data[id_],'version':'2'} if id_==FILE else self.drive.data[id_]): self.queue.poll()
        self.assertEqual(self.state(),('rejected',));self.assertFalse(self.calls)
    def test_invalid_receipt(self):
        with patch.object(self.queue,'call',return_value={'found':True,'published':True}): self.queue.poll()
        self.assertEqual(self.state(),('retry',))
    def test_duplicate_json(self):
        with self.assertRaises(Reject): parse_order(b'{"conta":"a","conta":"b"}',ACCOUNT,FILE)
    def test_too_large(self):
        with self.assertRaises(Reject): parse_order(b' '*65537,ACCOUNT,FILE)
    def test_stable_request_id(self):
        self.assertEqual(parse_order(self.drive.raw,ACCOUNT,FILE)['requestId'],REQUEST)
    def test_duplicate_upload_same_request(self):
        duplicate='second_order_1234567890'
        self.drive.data[duplicate]={**self.drive.data[FILE],'id':duplicate}
        self.queue.poll()
        self.assertEqual(len({request for _,request in self.calls}),1)
        self.assertEqual(len(self.calls),4)
    def test_inconsistent_filename(self):
        self.drive.data[FILE]['name']='ordem-wrong.json'; self.queue.poll()
        self.assertEqual(self.state(),('rejected',)); self.assertFalse(self.calls)
    def test_pagination_rejects_incomplete(self):
        drive=Drive.__new__(Drive)
        with patch.object(drive,'get',return_value={'files':[],'incompleteSearch':True}):
            with self.assertRaises(Reject): drive.children(ROOT)

if __name__=='__main__': unittest.main()
