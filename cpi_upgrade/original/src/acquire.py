from net import fetch,ROOT
from lxml import html
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta
import re,json

def jobs_run(jobs,n=14):
 with ThreadPoolExecutor(max_workers=n) as ex:
  fs={ex.submit(fetch,u,name):name for name,u in jobs}
  for i,f in enumerate(as_completed(fs),1):
   try:b=f.result();print(i,len(fs),fs[f],len(b),flush=True)
   except Exception as e:print('FAILED',fs[f],repr(e),flush=True)

def main():
 archive=html.fromstring(fetch('https://www.bls.gov/bls/news-release/cpi.htm','bls_archive.html'))
 events=[]
 for a in archive.xpath('//a'):
  u=a.get('href','');m=re.search(r'/archives/cpi_(\d{8})\.htm',u)
  if not m:continue
  date=datetime.strptime(m[1],'%m%d%Y')
  if datetime(2019,1,1)<=date<=datetime(2026,10,11):events.append({'date':date.strftime('%Y-%m-%d'),'reference_label':a.text_content().strip(),'url':'https://www.bls.gov'+u})
 events=sorted({x['date']:x for x in events}.values(),key=lambda x:x['date'])
 (ROOT/'data/calendar.json').write_text(json.dumps(events,indent=2))
 print('calendar',len(events),flush=True)
 jobs=[('bls/cpi_'+e['date']+'.html',e['url']) for e in events]
 days=sorted({(datetime.fromisoformat(e['date'])+timedelta(days=d)).strftime('%Y-%m-%d') for e in events for d in [0,1]})
 jobs += [('btc/BTCUSDT-1m-'+d+'.zip','https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-'+d+'.zip') for d in days]
 jobs += [('btc/BTCUSDT-1m-'+d+'.zip.CHECKSUM','https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-'+d+'.zip.CHECKSUM') for d in days]
 jobs += [('investing_'+k+'.html','https://www.investing.com/economic-calendar/'+slug) for k,slug in [('yoy','cpi-733'),('ism','ism-1483'),('fomc','interest-rate-decision-168'),('headline_mom','cpi-69'),('core_mom','core-cpi-56'),('core_yoy','core-cpi-736')] if not (ROOT/'data'/('investing_'+k+'.json')).exists()]
 jobs.append(('consensus.json','https://raw.githubusercontent.com/superpilot69/fred-us-macro-open-data/main/data/investing-us-macro-consensus.json'))
 if not (ROOT/'data/fee_schedule_facts.json').exists():jobs += [('fees/zero_fee_start.html','https://www.binance.com/en/support/announcement/detail/10435147c55d4a40b64fcbf43cb46329'),('fees/zero_fee_end.html','https://www.binance.com/en/support/announcement/detail/be13a645cca643d28eab5b9b34f2dc36'),('fees/spot_fee_faq.html','https://www.binance.com/en/support/faq/detail/e85d6e703b874674840122196b89780a')]
 jobs_run(jobs)
if __name__=='__main__':main()
