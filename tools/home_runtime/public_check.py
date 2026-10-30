"""One real historical issuer release through the installed selector and private socket."""
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SOURCES=(
 ('moex_fy2025','https://www.moex.com/n98156?nt=0',{'www.moex.com','moex.com'}),
 ('nornickel_fy2025','https://nornickel.ru/news-and-media/press-releases-and-news/nornikel-obyavlyaet-konsolidirovannye-finansovye-rezultaty-po-msfo-za-2025-god/',
  {'www.nornickel.ru','nornickel.ru'}))
WORDS=re.compile(r'выручк|чистая прибыль|чистого долга|чистый долг|дивиденд|ebitda|финансовы[ех] результат',re.I)


class Redirect(urllib.request.HTTPRedirectHandler):
    def __init__(self,hosts): self.hosts=hosts
    def redirect_request(self,req,fp,code,msg,headers,url):
        p=urllib.parse.urlsplit(url)
        if p.scheme!='https' or p.hostname not in self.hosts or p.username or p.password or p.port not in (None,443):
            raise ValueError('unexpected_public_redirect')
        return super().redirect_request(req,fp,code,msg,headers,url)


class Blocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tag=None
        self.buf=[]
        self.title=''
        self.rows=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('p','li','h1'):
            self.tag=tag
            self.buf=[]
    def handle_data(self,data):
        if self.tag: self.buf.append(data)
    def handle_endtag(self,tag):
        if tag!=self.tag: return
        text=' '.join(''.join(self.buf).split())
        if tag=='h1' and text and not self.title: self.title=text[:395]
        if tag in ('p','li') and WORDS.search(text) and 25<=len(text) and len(text.encode())<=950 and text not in self.rows:
            self.rows.append(text)
        self.tag=None
        self.buf=[]


def main():
    if os.geteuid()==0: raise ValueError('unprivileged_reader_required')
    sys.path.insert(0,'/opt/analyst-source/853090e11dcefef693366159c97316e55045c4c9/backend')
    import local_research
    failures=[]
    for source,url,hosts in SOURCES:
        try:
            op=urllib.request.build_opener(Redirect(hosts))
            with op.open(urllib.request.Request(url,headers={'User-Agent':'AnalystAI-public-research/1.0','Accept-Encoding':'identity'}),timeout=12) as resp:
                if resp.status!=200: raise ValueError('publication_unavailable')
                raw=resp.read(3*1024**2+1)
                if len(raw)>3*1024**2: raise ValueError('publication_too_large')
                enc=resp.headers.get_content_charset() or 'utf-8'
            parser=Blocks()
            parser.feed(raw.decode(enc))
            if not parser.title or not parser.rows: raise ValueError('public_text_unavailable')
            paragraphs=parser.rows[:3]
            body='\n'.join(paragraphs)
            started=time.monotonic()
            result=local_research.select_public_fragments(parser.title,body,enabled=True)
            if result.get('status')!='source_excerpt_selection':
                failures.append({'source':source,'reason':result.get('status','unknown')});continue
            expected=hashlib.sha256((parser.title+'\n'+body).encode()).hexdigest()
            if result.get('source_sha256')!=expected or result.get('trade_permission') is not False:
                raise ValueError('provenance_mismatch')
            excerpts=result.get('excerpts',[])
            if not all(type(x.get('id')) is int and 0<=x['id']<len(paragraphs) and x['text']==paragraphs[x['id']] for x in excerpts):
                raise ValueError('excerpt_mismatch')
            return {'status':'verified','source':source,'url':url,'published_period':'FY2025','http':200,
                    'raw_sha256':hashlib.sha256(raw).hexdigest(),'source_sha256':expected,'model_sha256':result['model_sha256'],
                    'exact_excerpts':len(excerpts),'seconds':round(time.monotonic()-started,2),'trade_permission':False}
        except (ValueError,OSError,UnicodeError) as err:
            failures.append({'source':source,'reason':type(err).__name__})
    return {'status':'blocked','sources':failures}


if __name__=='__main__':
    answer=main()
    print(json.dumps(answer))
    raise SystemExit(0 if answer['status']=='verified' else 1)
