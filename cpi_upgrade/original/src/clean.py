from net import ROOT
import pandas as pd,numpy as np,json,re,zipfile,io
from lxml import html
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

def num(v):
 try:return float(v.replace(',','').strip())
 except (ValueError,AttributeError):return np.nan

def occurrences(name):
 p=ROOT/'raw'/name
 if not p.exists():
  fallback=ROOT/'data'/name.replace('.html','.json')
  return json.loads(fallback.read_text()).get('occurrences',[]) if fallback.exists() else []
 s=p.read_text();m=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',s)
 if not m:return []
 x=json.loads(m[1])['props']['pageProps']['state']['economicCalendarEventStore']
 rs=x.get('occurrences',[])
 # Preserve only public event data, omit unrelated page/session metadata.
 (ROOT/'data'/name.replace('.html','.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2))
 return rs

def build_events():
 es=json.loads((ROOT/'data/calendar.json').read_text())
 occ={k:{r['occurrence_time'][:10]:r for r in occurrences(name)} for k,name in [('headline_yoy','investing_yoy.html'),('headline_mom','investing_headline_mom.html'),('core_yoy','investing_core_yoy.html'),('core_mom','investing_core_mom.html')]}
 # fallback explicit raw occurrence records, not FRED transformed/revised values
 fallback=json.loads((ROOT/'raw/consensus.json').read_text())
 for ser in fallback['series']:
  key={733:'headline_yoy',736:'core_yoy'}.get(ser['eventId'])
  if not key:continue
  for r in ser['occurrences']:
   d=r['occurrenceTime'][:10]
   if d not in occ[key]:occ[key][d]=r
 rows=[];aud=[]
 for e in es:
  d=e['date'];t0=datetime.fromisoformat(d+'T08:30:00').replace(tzinfo=ZoneInfo('America/New_York')).astimezone(ZoneInfo('UTC'))
  row={**e,'t0_utc':t0.isoformat(),'year':int(d[:4]),'release_et':'08:30:00','cpi_status':'missing_news_release'}
  p=ROOT/'raw/bls'/f'cpi_{d}.html'
  if p.exists():
   h=html.fromstring(p.read_bytes());pre='\n'.join(h.xpath('//pre//text()'));text=h.text_content()
   ptext=ROOT/'data/bls_text'/f'cpi_{d}.txt';ptext.parent.mkdir(exist_ok=True);ptext.write_text(pre or text)
   row['embargo_0830_verified']=bool(re.search(r'8:30\s*a\.m\.',pre))
   # Table 1 contains 7 seasonally-adjusted MoM changes and last column NSA YoY.
   first={}
   for tr in h.xpath('//table//tr'):
    cells=[re.sub(r'\s+',' ',c.text_content()).strip() for c in tr.xpath('./th|./td')]
    if not cells:continue
    label=cells[0]
    if label in ['All items','All items less food and energy','Energy','Shelter','Services less energy services'] and label not in first:
     first[label]=cells
   for label,key in [('All items','headline'),('All items less food and energy','core'),('Energy','energy'),('Shelter','shelter'),('Services less energy services','services_ex_energy')]:
    cs=first.get(label,[])
    if len(cs)>=3:
     if len(cs)==10: # Older archive exposes full Table 2 before summary table
      row[key+'_mom_actual']=num(cs[-1]);row[key+'_yoy_actual']=num(cs[5])
     elif len(cs)==9:
      row[key+'_mom_actual']=num(cs[-2]);row[key+'_yoy_actual']=num(cs[-1])
     else: raise ValueError(f'Unexpected CPI row layout {d} {label} {cs}')
   row['cpi_status']='official_table_parsed' if all(np.isfinite(row.get(k+'_yoy_actual',np.nan)) for k in ['headline','core']) else 'parse_incomplete'
  for k in occ:
   rr=occ[k].get(d,{})
   row[k+'_forecast']=rr.get('forecast',np.nan)
   row[k+'_calendar_actual']=rr.get('actual',np.nan)
   row[k+'_occurrence_id']=rr.get('occurrence_id',rr.get('occurrenceId',''))
   row[k+'_forecast_source']='https://www.investing.com/economic-calendar/'+{'headline_yoy':'cpi-733','headline_mom':'cpi-69','core_yoy':'core-cpi-736','core_mom':'core-cpi-56'}[k] if rr else ''
   act=row.get(k+'_actual',np.nan);ca=rr.get('actual',np.nan);f=rr.get('forecast',np.nan)
   row[k+'_calendar_matches_bls']=bool(np.isfinite(act) and ca is not None and np.isfinite(ca) and abs(act-ca)<0.051)
   row[k+'_surprise_pp']=round(act-f,1) if np.isfinite(act) and f is not None and np.isfinite(f) else np.nan
   s=row[k+'_surprise_pp'];row[k+'_class']='missing' if pd.isna(s) else ('hot' if s>0 else 'cold' if s<0 else 'inline')
   row[k+'_size']='missing' if pd.isna(s) else ('inline' if s==0 else 'mild' if abs(s)<0.2 else 'large')
  for period in ['yoy','mom']:
   a=row['headline_'+period+'_class'];b=row['core_'+period+'_class'];row['combo_'+period]=a+'_'+b
  row['scheduled_jobless_claims']=t0.weekday()==3
  rows.append(row)
 df=pd.DataFrame(rows);df.to_csv(ROOT/'data/events_cpi.csv',index=False,float_format='%.10g');print('CPI',df.shape,df.cpi_status.value_counts().to_dict())
 for k in occ:print(k,'forecasts',df[k+'_forecast'].notna().sum(),'match',df[k+'_calendar_matches_bls'].sum(),'disagreement',df.loc[df[k+'_actual'].notna()&df[k+'_calendar_actual'].notna()&~df[k+'_calendar_matches_bls'],['date',k+'_actual',k+'_calendar_actual']].to_dict('records'))
 return df

def load_day(day):
 p=ROOT/'raw/btc'/f'BTCUSDT-1m-{day}.zip'
 if not p.exists():return pd.DataFrame()
 with zipfile.ZipFile(p) as z:
  f=z.open(z.namelist()[0]);df=pd.read_csv(f,header=None)
 df.columns=['open_time','open','high','low','close','volume','close_time','quote_volume','trades','taker_base','taker_quote','ignore']
 df['open_time']=pd.to_numeric(df['open_time'],errors='coerce');df=df.dropna(subset=['open_time'])
 # Binance Spot changed timestamps to microseconds starting 2025-01-01.
 unit='us' if df.open_time.median()>1e14 else 'ms'
 df['ts']=pd.to_datetime(df.open_time,unit=unit,utc=True)
 df['source_unit']=unit
 for c in ['open','high','low','close','volume']:df[c]=pd.to_numeric(df[c],errors='coerce')
 return df.set_index('ts').sort_index()

def build_btc(es):
 audits=[]
 for _,e in es.iterrows():
  d=e['date'];t0=pd.Timestamp(e.t0_utc);nextday=(datetime.fromisoformat(d)+timedelta(days=1)).strftime('%Y-%m-%d')
  dfs=[load_day(d),load_day(nextday)];dfs=[x for x in dfs if not x.empty]
  if not dfs:audits.append({'date':d,'status':'missing_both_days'});continue
  df=pd.concat(dfs);dups=df.index.duplicated().sum()
  if dups:
   audits.append({'date':d,'status':'duplicate_timestamps','duplicates':int(dups)});continue
  df=df.loc[t0-pd.Timedelta(minutes=60):t0+pd.Timedelta(minutes=1440)].copy()
  idx=pd.date_range(t0-pd.Timedelta(minutes=60),t0+pd.Timedelta(minutes=1440),freq='min')
  missing=idx.difference(df.index)
  bad=((df[['open','high','low','close']]<=0).any(axis=1)|(df.high<df[['open','close']].max(axis=1))|(df.low>df[['open','close']].min(axis=1))|(df.high<df.low)|df[['open','high','low','close']].isna().any(axis=1))
  jump=np.log(df.close).diff().abs();flags=df.index[jump>0.1]
  audit={'date':d,'status':'complete' if len(missing)==0 and bad.sum()==0 else 'incomplete','expected_rows':1501,'actual_rows':len(df),'missing_minutes':len(missing),'duplicates':int(dups),'bad_ohlc':int(bad.sum()),'jump_over10pct':len(flags),'timestamp_unit':','.join(df.source_unit.unique()),'missing_utc':';'.join(t.isoformat() for t in missing),'flags_utc':';'.join(t.isoformat() for t in flags)}
  audits.append(audit)
  dest=ROOT/'data'/f'btc_{d}.csv.gz';tmp=dest.with_name(dest.name+'.part')
  df.reset_index()[['ts','open','high','low','close','volume','quote_volume','trades']].to_csv(tmp,index=False,compression={'method':'gzip','mtime':0})
  if tmp.stat().st_size<20:raise ValueError(f'Failed compressed CSV write {d}')
  tmp.replace(dest)
 pd.DataFrame(audits).to_csv(ROOT/'results/btc_audit.csv',index=False);print('BTC',pd.DataFrame(audits).status.value_counts().to_dict())
if __name__=='__main__':build_btc(build_events())
