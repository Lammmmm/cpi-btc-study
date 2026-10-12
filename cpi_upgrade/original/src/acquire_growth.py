from acquire import jobs_run
from net import ROOT
from datetime import datetime,timedelta
import json
es=json.loads((ROOT/'data/calendar.json').read_text());jobs=[]
for e in es:
 vd=(datetime.fromisoformat(e['date'])-timedelta(days=1)).strftime('%Y-%m-%d')
 start=(datetime.fromisoformat(e['date'])-timedelta(days=500)).strftime('%Y-%m-%d')
 for sid in ['UNRATE','PAYEMS','PCEC96','DFEDTARU']:
  url=f'https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={sid}&cosd={start}&coed={vd}&vintage_date={vd}'
  jobs.append((f'vintages/{e["date"]}_{sid}.csv',url))
jobs_run(jobs,16)
