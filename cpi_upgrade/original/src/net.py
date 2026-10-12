from pathlib import Path
import urllib.request, hashlib, json, time, socket, threading
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
LOCK=threading.Lock()
def shipped_input(path):
 r=str(path.relative_to(ROOT))
 if r.startswith('raw/'):
  return r in ['raw/bls_archive.html','raw/consensus.json','raw/download_log.jsonl'] or any(r.startswith('raw/'+s+'/') for s in ['bls','btc','vintages','coinbase'])
 if r.startswith('data/fees/'):return False  # Structured announcement facts replace article prose.
 return r.startswith(('data/','fonts/'))
socket.setdefaulttimeout(25)
def fetch(url, name=None, retries=2):
 p=ROOT/'raw'/(name or hashlib.sha256(url.encode()).hexdigest())
 if p.exists():return p.read_bytes()
 for attempt in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 CPI historical research'})
   with urllib.request.urlopen(req,timeout=25) as r:
    b=r.read(); status=r.status
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
   row={'url':url,'file':str(p.relative_to(ROOT)),'utc':datetime.now(timezone.utc).isoformat(),'status':status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
   with LOCK:
    with (ROOT/'raw/download_log.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
   return b
  except Exception as e:
   if attempt==retries-1:
    with LOCK:
     with (ROOT/'raw/download_log.jsonl').open('a') as f:f.write(json.dumps({'url':url,'utc':datetime.now(timezone.utc).isoformat(),'error':repr(e)})+'\n')
    raise
