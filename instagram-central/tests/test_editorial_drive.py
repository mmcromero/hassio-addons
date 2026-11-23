"""Drive scope and byte checks: synthetic IDs, fake read-only transport, no Google keys."""
from copy import deepcopy
import hashlib
import tempfile
import unittest
from pathlib import Path

from editorial_connections import Connections, Denied
import editorial_drive as drive

ROOT = 'synthetic_root_01'
FOLDER = 'synthetic_folder_01'
FILE = 'synthetic_file_01'
RAW = b'\x89PNG\r\n\x1a\nsynthetic fixture'
ITEM = {'fileId': FILE, 'mime': 'image/png', 'bytes': len(RAW), 'sha256': hashlib.sha256(RAW).hexdigest()}


class FakeReader:
    def __init__(self):
        self.records = {
            ROOT: {'id':ROOT,'name':'Inbox','mimeType':drive.FOLDER,'trashed':False,'version':'1'},
            FOLDER: {'id':FOLDER,'name':'primary','mimeType':drive.FOLDER,'trashed':False,'parents':[ROOT],'version':'1'},
            FILE: {'id':FILE,'name':'mock.png','mimeType':'image/png','trashed':False,'parents':[FOLDER],
                   'size':str(len(RAW)),'version':'2','capabilities':{'canDownload':True}},
        }
        self.raw, self.media_reads, self.mutate = RAW, 0, None
    def get(self, fid, *, media=False, limit=65536):
        if media:
            self.media_reads += 1
            if self.mutate: self.mutate()
            return self.raw
        return deepcopy(self.records[fid])


class DriveTests(unittest.TestCase):
    def test_exact_binary_and_checksum(self):
        f = FakeReader()
        self.assertEqual(drive.read_verified(f, ROOT, 'primary', ITEM), RAW)
        f.records[FILE]['sha256Checksum'] = ITEM['sha256']
        self.assertEqual(drive.read_verified(f, ROOT, 'primary', ITEM), RAW)
        self.assertEqual(f.media_reads, 2)

    def test_wrong_account_root_and_public_are_rejected_before_media(self):
        for changes in [('account','other'),('parent','wrong_root_123'),('public',True),('shortcut',True),('trash',True)]:
            f = FakeReader()
            account = 'primary'
            if changes[0]=='account': account=changes[1]
            elif changes[0]=='parent': f.records[FOLDER]['parents']=[changes[1]]
            elif changes[0]=='public': f.records[FILE]['permissions']=[{'type':'anyone','role':'reader'}]
            elif changes[0]=='shortcut': f.records[FILE]['mimeType']='application/vnd.google-apps.shortcut'
            elif changes[0]=='trash': f.records[FILE]['trashed']=True
            with self.assertRaises(Denied): drive.read_verified(f, ROOT, account, ITEM)
            self.assertEqual(f.media_reads,0)

    def test_tampering_size_hash_and_move(self):
        f=FakeReader(); f.raw=RAW[:-1]+b'X'
        with self.assertRaises(Denied): drive.read_verified(f,ROOT,'primary',ITEM)
        f=FakeReader(); f.raw=RAW+b'x'
        with self.assertRaises(Denied): drive.read_verified(f,ROOT,'primary',ITEM)
        f=FakeReader(); f.mutate=lambda: f.records[FILE].update(version='3')
        with self.assertRaises(Denied): drive.read_verified(f,ROOT,'primary',ITEM)
        f=FakeReader(); f.mutate=lambda: f.records[FOLDER].update(parents=['wrong_root_123'])
        with self.assertRaises(Denied): drive.read_verified(f,ROOT,'primary',ITEM)

    def test_reject_untrusted_reference_and_missing_credentials(self):
        for item in [{**ITEM,'fileId':'https://example.test/file'},{**ITEM,'bytes':True},{**ITEM,'sha256':'x'}]:
            with self.assertRaises(Denied): drive.read_verified(FakeReader(), ROOT, 'primary', item)
        with self.assertRaises(Denied): drive.download('',ROOT,'primary',ITEM)
        self.assertRaises(Denied,drive.read_verified,FakeReader(),'', 'primary',ITEM)

    def test_root_grant_is_exclusive_and_revisable(self):
        with tempfile.TemporaryDirectory() as t:
            accounts=lambda:[{'business_id':'primary','display_name':'Primary','username':'primary','enabled':True,'instagram_account_id':'synthetic'}]
            c=Connections(Path(t)/'grants.sqlite',accounts)
            first=c.create('one','owner_all',[],ROOT)
            with self.assertRaises(Denied): c.create('two','owner_all',[],ROOT)
            second=c.create('two','selected',['primary'])
            with self.assertRaises(Denied): c.update_drive(second['id'],ROOT)
            c.update_drive(first['id'],'synthetic_root_02')
            c.update_drive(second['id'],ROOT)
            with c.authorize(second['token']) as (row, allowed):
                self.assertEqual(row['drive_root'],ROOT)
                self.assertEqual([a['id'] for a in allowed],['primary'])
            c.revoke(second['id'])
            with self.assertRaises(Denied): c.update_drive(second['id'],'synthetic_root_03')


if __name__ == '__main__': unittest.main()
