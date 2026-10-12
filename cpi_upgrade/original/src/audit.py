"""Source manifest and field dictionary, based on saved input files and event data."""
from net import ROOT,shipped_input
import pandas as pd,json,hashlib

def main():
 log=[]
 for line in (ROOT/'raw/download_log.jsonl').read_text().splitlines():
  try:log.append(json.loads(line))
  except json.JSONDecodeError:continue
 byfile={r.get('file'):r for r in log if r.get('file')}
 rows=[];excluded=[]
 # Public JSON economic calendar extracts replace full page session/ad metadata.
 omitted=set(p.name for p in (ROOT/'raw').glob('investing_*.html'))
 for directory in ['raw','data','fonts']:
  for p in sorted((ROOT/directory).rglob('*')):
   if not p.is_file():continue
   name=str(p.relative_to(ROOT));r=byfile.get(name,{})
   if not shipped_input(p):
    excluded.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':r.get('url',''),'acquired_utc':r.get('utc','derived'),'reason':'diagnostic/nonessential original or article/session HTML; numeric public snapshots retained where needed'})
    continue
   if p.parent==ROOT/'data' and p.name.startswith('investing_'):
    r=byfile.get('raw/'+p.name.replace('.json','.html'),{})
   rows.append({'file':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':r.get('url','derived/frozen input; see README'),'acquired_utc':r.get('utc','derived'),'http_status':r.get('status',''),'original_or_derived':'original' if directory=='raw' else 'derived or sanitized public source'})
 pd.DataFrame(rows).to_csv(ROOT/'results/source_manifest.csv',index=False)
 cols=['file','sha256','url','acquired_utc','reason'];xp=ROOT/'results/source_exclusion_audit.csv'
 if xp.exists():
  try:
   prior=pd.read_csv(xp).to_dict('records');excluded=list({r['file']:r for r in prior+excluded}.values())
  except pd.errors.EmptyDataError:pass
 pd.DataFrame(excluded,columns=cols).to_csv(xp,index=False)
 pd.DataFrame([r for r in log if r.get('error')]).to_csv(ROOT/'results/download_errors.csv',index=False)
 e=pd.read_csv(ROOT/'results/table_G_events.csv');dic=[]
 for c in e:
  unit=''
  if c.endswith('_pp'):unit='percentage points (0.1=0.1pp)'
  elif c.startswith('first_return_'):unit='15m first-wave return; suffix is target horizon, not first-wave length; decimal (0.01=1%)'
  elif c.startswith(('first_reverse5_min_','baseline_exit_min_')):unit='minutes since CPI; blank also means no trigger, check status and reverse5_touch flags'
  elif c.startswith('2Y_return_'):unit='unverified empty placeholder; future yield signal must use yield_delta_bp, not a fractional yield return'
  elif any(k in c for k in ['return','mfe','mae','sigma']):unit='decimal fractional return (0.01=1%)'
  elif any(k in c for k in ['_actual','_forecast','_latest']) and not any(k in c for k in ['price','ism','PAYEMS','PCEC96']):unit='percentage rate where CPI/rate; see README'
  elif any(k in c for k in ['keep','touch','_end','win','bad','continuous','verified','matches','promotion']):unit='0/1 flag where numeric; blank is unknown, not 0'
  elif any(k in c for k in ['price','extreme','p0']):unit='USDT per BTC'
  elif c.endswith('_bps'):unit='basis points (24=0.24%)'
  elif 'minute' in c or '_min' in c:unit='minutes since CPI'
  dic.append({'field':c,'dtype':str(e[c].dtype),'unit_or_interpretation':unit,'nonmissing_events':int(e[c].notna().sum()),'missing_events':int(e[c].isna().sum())})
 pd.DataFrame(dic).to_csv(ROOT/'results/event_field_dictionary.csv',index=False)
 print('source inventory',len(rows),'event fields',len(dic))
if __name__=='__main__':main()
