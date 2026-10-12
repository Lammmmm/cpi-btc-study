from net import ROOT,fetch
from acquire import jobs_run
from backtest import calc
from urllib.parse import urlencode
import pandas as pd,numpy as np,json

def acquire():
 es=pd.read_csv(ROOT/'data/events_cpi.csv');jobs=[]
 for _,e in es.iterrows():
  t0=pd.Timestamp(e.t0_utc);start=t0-pd.Timedelta(minutes=35);end=t0+pd.Timedelta(minutes=242)
  u='https://api.exchange.coinbase.com/products/BTC-USD/candles?'+urlencode({'granularity':60,'start':start.isoformat(),'end':end.isoformat()})
  jobs.append((f'coinbase/{e["date"]}.json',u))
 jobs_run(jobs,10)

def verify():
 es=pd.read_csv(ROOT/'data/events_cpi.csv');b=pd.read_csv(ROOT/'results/event_paths.csv');rows=[];paths=[]
 for _,e in es.iterrows():
  p=ROOT/'raw/coinbase'/f'{e["date"]}.json'
  if not p.exists():rows.append({'date':e['date'],'status':'download_failed'});continue
  r=json.loads(p.read_text())
  if not isinstance(r,list):rows.append({'date':e['date'],'status':'invalid_response'});continue
  df=pd.DataFrame(r,columns=['epoch','low','high','open','close','volume']);df['ts']=pd.to_datetime(df.epoch,unit='s',utc=True);df=df.set_index('ts').sort_index()
  if df.index.duplicated().sum():rows.append({'date':e['date'],'status':'duplicates'});continue
  t0=pd.Timestamp(e.t0_utc);need=pd.date_range(t0-pd.Timedelta(minutes=1),t0+pd.Timedelta(minutes=240),freq='min');missing=need.difference(df.index)
  row={'date':e['date'],'status':'complete' if len(missing)==0 else 'gaps','n':len(df),'missing_minutes':len(missing)}
  for h in [30,60,240]:
   a=calc(df,t0,15,h)
   paths.append({'date':e['date'],'horizon_min':h,**a})
   binrow=b.loc[(b.date==e['date'])&(b.confirm_min==15)&(b.horizon_min==h)&(b.status=='ok')]
   if a['status']=='ok' and len(binrow):
    bb=binrow.iloc[0];row[f'first_return_diff_{h}m_bps']=(a['first_return']-bb.first_return)*10000;row[f'release_return_diff_{h}m_bps']=(a['release_return']-bb.release_return)*10000;row[f'direction_agrees_{h}m']=a['direction']==bb.direction;row[f'keep_agrees_{h}m']=a['keep']==bb.keep;row[f'reverse_agrees_{h}m']=a['reverse5_touch']==bb.reverse5_touch;row[f'net_return_diff_{h}m_bps']=(a['net_return']-bb.net_return)*10000
  rows.append(row)
 pd.DataFrame(rows).to_csv(ROOT/'results/crossvenue_audit.csv',index=False);pd.DataFrame(paths).to_csv(ROOT/'results/coinbase_event_paths.csv',index=False);print(pd.DataFrame(rows).status.value_counts().to_dict())
if __name__=='__main__':
 acquire()
 verify()
