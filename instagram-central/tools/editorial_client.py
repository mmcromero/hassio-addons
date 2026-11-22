#!/usr/bin/env python3
"""Generic API client. Dry run by default; credentials only from environment."""
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirecionamento recusado; confira o endereço da Central.')


class Client:
    def __init__(self, base_url, token):
        origin = urlsplit(base_url)
        if origin.scheme != 'https' or not origin.netloc or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('','/'):
            raise ValueError('Use somente a origem HTTPS da Central, sem caminho ou credenciais.')
        if not re.fullmatch(r'cei1\.[a-z][a-z0-9_-]{1,39}\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}',token):
            raise ValueError('Chave da integração inválida.')
        self.base,self.token = base_url.rstrip('/'),token
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, action, data, *, upload=False, request_id=None, index=None, mime=None):
        headers={'Authorization':'Bearer '+self.token,'X-Editorial-Action':'import_'+action}
        if upload:
            headers.update({'Content-Type':mime,'X-Import-Id':request_id,'X-Media-Index':str(index)})
            body=data
        else:
            headers['Content-Type']='application/json';body=json.dumps(data).encode()
        req=urllib.request.Request(self.base+'/editorial/api/'+('media' if upload else 'drafts'),body,headers,method='POST')
        try:
            with self.opener.open(req,timeout=120) as response:
                raw=response.read(1024*1024+1)
                if len(raw)>1024*1024: raise ValueError('Resposta acima do limite.')
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            try: message=json.loads(exc.read(4096)).get('error','Pedido recusado.')
            except (ValueError,UnicodeDecodeError): message='Pedido recusado.'
            raise ValueError(f'HTTP {exc.code}: {message}') from None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format',choices=['feed','carousel','story','reel'],required=True)
    parser.add_argument('--caption-file',type=Path,required=True)
    parser.add_argument('--media',type=Path,nargs='+',required=True,help='Arquivos na ordem da publicação')
    parser.add_argument('--request-id',help='Reutilize o mesmo ID em tentativas da mesma transferência')
    parser.add_argument('--approved',action='store_true',help='O proprietário autorizou transferir este conteúdo')
    parser.add_argument('--publish-now',action='store_true')
    parser.add_argument('--publish-approved',action='store_true',help='O proprietário autorizou a publicação direta deste conteúdo')
    parser.add_argument('--instagram-account-id',help='Conta de destino confirmada para a publicação direta')
    args=parser.parse_args(argv)
    if args.publish_now and (not args.approved or not args.publish_approved or not args.instagram_account_id):
        parser.error('Publicação direta exige --approved --publish-approved e --instagram-account-id.')
    if args.publish_approved and not args.publish_now: parser.error('Use --publish-approved somente com --publish-now.')
    caption=args.caption_file.read_text(encoding='utf-8').rstrip('\n')
    if len(caption)>2200: raise ValueError('Legenda acima de 2200 caracteres.')
    if not (2<=len(args.media)<=20 if args.format=='carousel' else len(args.media)==1): raise ValueError('Quantidade de arquivos incompatível.')
    files=[]
    for path in args.media:
        size=path.stat().st_size
        if not 0<size<=25*1024*1024: raise ValueError('Arquivo vazio ou acima de 25 MiB.')
        mime=mimetypes.guess_type(path)[0]
        if mime not in ('image/png','image/jpeg','video/mp4'): raise ValueError('Tipo de arquivo não suportado.')
        raw=path.read_bytes();files.append((raw,mime))
    digest=hashlib.sha256(json.dumps({'format':args.format,'caption':caption,'files':[
        {'sha256':hashlib.sha256(raw).hexdigest(),'mime':mime} for raw,mime in files]},sort_keys=True).encode()).hexdigest()
    request=args.request_id or 'content_'+digest
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',request): raise ValueError('Request ID inválido.')
    if not args.approved:
        print(json.dumps({'dryRun':True,'requestId':request,'files':len(files),'format':args.format,'networkRequests':0},ensure_ascii=False));return 0
    client=Client(os.environ.get('CENTRAL_EDITORIAL_URL',''),os.environ.get('CENTRAL_EDITORIAL_TOKEN',''))
    result=client.call('receipt',{'requestId':request})
    if result['found']:
        if result['contentDigest']!=digest: raise ValueError('Request ID já utilizado com outro conteúdo.')
        if result['status']=='deleted': raise ValueError('Transferência já excluída. Use novo --request-id para importar novamente.')
    else:
        media=[]
        for index,(raw,mime) in enumerate(files):
            result=client.call('upload',raw,upload=True,request_id=request,index=index,mime=mime);media.append(result['id'])
        result=client.call('commit',{'schemaVersion':1,'requestId':request,'transferApproved':True,
             'format':args.format,'caption':caption,'mediaIds':media,'contentDigest':digest})
    if args.publish_now:
        result=client.call('publish',{'requestId':request,'version':result['importedVersion'],
            'instagramAccountId':args.instagram_account_id,'publishApproved':True})
    print(json.dumps({'requestId':request,**result},ensure_ascii=False))
    return 0


if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,OSError,urllib.error.URLError):
        print('Operação não confirmada. Confira configuração/conexão e consulte o recibo antes de repetir. Use o mesmo request-id; nenhuma nova tentativa de publicação é feita automaticamente.',file=sys.stderr)
        sys.exit(1)
