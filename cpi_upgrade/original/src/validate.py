from net import ROOT
from backtest import calc
from clean import load_day
from summarize import wilson
from growth import monthly_series,classify
import pandas as pd,numpy as np,hashlib,json,gzip

def synthetic_test():
 # Flat prehistory, known first move, then pullback retaining original direction.
 t0=pd.Timestamp('2024-01-11T13:30:00Z');idx=pd.date_range(t0-pd.Timedelta(minutes=60),t0+pd.Timedelta(minutes=30),freq='min')
 df=pd.DataFrame(index=idx,columns=['open','high','low','close'],data=100000.)
 for m in range(15):
  p=100000.+1000*(m+1)/15;df.loc[t0+pd.Timedelta(minutes=m),:]=p
 df.loc[t0+pd.Timedelta(minutes=15):,:]=101000.
 df.loc[t0+pd.Timedelta(minutes=29):,:]=100500.
 r=calc(df,t0,15,30)
 assert r['keep']==1 and r['gross_return']<0 and r['net_win']==0
 assert r['fade50_touch']==1 and r['fade100_touch']==0 and r['reverse5_touch']==0
 assert r['entry_utc']=='2024-01-11T13:46:00+00:00'
 df.loc[t0+pd.Timedelta(minutes=29):,:]=99000.
 r=calc(df,t0,15,30);assert r['reverse5_touch']==1 and r['first_reverse5_min']==30
 df=df.drop(t0+pd.Timedelta(minutes=20));assert calc(df,t0,15,30)['status']=='missing_in_required_window'
 # Opposite case: initial fall, partial rebound; baseline side != trade profit.
 df=pd.DataFrame(index=idx,columns=['open','high','low','close'],data=100000.)
 df.loc[t0:t0+pd.Timedelta(minutes=14),:]=99000.;df.loc[t0+pd.Timedelta(minutes=15):,:]=99000.;df.loc[t0+pd.Timedelta(minutes=29):,:]=99500.
 r=calc(df,t0,15,30);assert r['direction']==-1 and r['keep']==1 and r['gross_return']<0 and r['fade50_touch']==1
 # Shutdown missing month must not silently stretch a 3-month lookback to 4 months.
 m=pd.DataFrame({'month':['2025-07-01','2025-08-01','2025-09-01','2025-11-01','2025-12-01','2026-01-01'],'value':[4.2,4.3,4.4,4.6,4.4,4.3]});s=monthly_series(m)
 assert s.get(s.index[-1]-3,np.nan)!=s.get(s.index[-1]-3,np.nan)
 assert abs(s.loc[pd.Period('2025-11','M')]-s.loc[pd.Period('2025-08','M')]-.3)<1e-9
 assert classify([np.nan,0,np.nan])=='unclassified' and classify([np.nan,0,0])=='stable'
 print('Synthetic accounting and missing-data tests PASS')

def main():
 synthetic_test()
 es=pd.read_csv(ROOT/'data/events_cpi.csv');pa=pd.read_csv(ROOT/'results/event_paths.csv');g=pd.read_csv(ROOT/'results/table_G_events.csv')
 assert len(es)==92 and len(g)==92 and es.date.nunique()==92
 assert es.embargo_0830_verified.all()
 assert es.groupby('year').size().to_dict()=={2019:12,2020:12,2021:12,2022:12,2023:12,2024:12,2025:11,2026:9}
 gr=pd.read_csv(ROOT/'data/growth.csv');assert gr.growth_strict.value_counts().to_dict()=={'unclassified':57,'stable':29,'deteriorating':6}
 shut=gr[gr.date=='2026-02-13'].iloc[0];assert pd.isna(shut.unrate_3m_change_pp) and pd.isna(shut.employment_bad) and shut.growth_strict=='unclassified' and shut.growth_snapshot=='stable'
 ba=pd.read_csv(ROOT/'results/btc_audit.csv');assert len(ba)==92 and ba.duplicates.sum()==0 and ba.bad_ohlc.sum()==0 and ba.jump_over10pct.sum()==0 and ba.missing_minutes.sum()==79
 for k in ['headline_yoy','core_yoy']:assert es[k+'_calendar_matches_bls'].all() and es[k+'_forecast'].notna().all()
 for k in ['headline_mom','core_mom']:assert es[k+'_calendar_matches_bls'].sum()==91 and es[k+'_forecast'].notna().sum()==91
 assert pa.groupby(['confirm_min','horizon_min']).size().eq(92).all()
 assert len(pa[pa.status!='ok'])==3
 valid=pa[pa.status=='ok']
 assert (valid.reverse5_touch<=valid.fade100_touch).all()
 assert (valid.fade100_touch<=valid.fade50_touch).all()
 assert np.allclose(valid.net_return,valid.gross_return-.0024,atol=1e-10)
 assert (pd.to_datetime(valid.entry_utc,utc=True)>pd.to_datetime(valid.t0_utc,utc=True)+pd.to_timedelta(valid.confirm_min,unit='min')).all()
 # Independent direct raw-archive reaggregation vs selected parsed event CSV for every event.
 errs=[]
 for _,e in es.iterrows():
  raw=load_day(e['date']);t0=pd.Timestamp(e.t0_utc);r15=raw.loc[t0+pd.Timedelta(minutes=14),'close']/raw.loc[t0-pd.Timedelta(minutes=1),'close']-1
  got=valid[(valid.date==e['date'])&(valid.confirm_min==15)&(valid.horizon_min==30)].iloc[0]
  errs.append(abs(r15-got.first_return))
 assert max(errs)<1e-10
 # Audit legacy named fourteen, without accepting old success labels.
 legacy=['2021-02-10','2021-07-13','2022-02-10','2022-05-11','2022-07-13','2022-08-10','2022-09-13','2023-02-14','2024-02-13','2024-04-10','2024-06-12','2024-10-10','2025-02-12','2025-12-18'];rows=[]
 for _,e in es.iterrows():
  raw=load_day(e['date']);t0=pd.Timestamp(e.t0_utc);p0=raw.loc[t0,'open'];p5=raw.loc[t0+pd.Timedelta(minutes=4),'close'];p10=raw.loc[t0+pd.Timedelta(minutes=9),'close'];o5=raw.loc[t0+pd.Timedelta(minutes=5),'open'];r10=p10/p0-1;s=int(np.sign(r10));sur=e.headline_yoy_surprise_pp
  same=np.sign(p5-p0)==np.sign(p10-o5) and np.sign(p5-p0)!=0;aligned=(sur>0 and s==-1) or (sur<0 and s==1)
  eligible=abs(r10)>=.005 and same and aligned
  row={'date':e['date'],'legacy_named14':e['date'] in legacy,'recomputed_eligible':eligible,'r10_raw_open':r10,'consecutive_same':same,'cpi_aligned':aligned,'headline_yoy_surprise_pp':sur}
  for h in [30,60,240]:
   ret=raw.loc[t0+pd.Timedelta(minutes=h-1),'close']/p0-1
   row[f'legacy_keep_{h}m']=s*ret>=.0025;row[f'legacy_reverse_{h}m']=s*ret<=-.0025
   bt=valid[(valid.date==e['date'])&(valid.confirm_min==10)&(valid.horizon_min==h)].iloc[0];row[f'net_return_entry11_{h}m']=bt.net_return
  rows.append(row)
 pd.DataFrame(rows).to_csv(ROOT/'results/legacy_audit.csv',index=False)
 report={'synthetic_tests':'pass','events':92,'short_window_events':92,'24h_events':91,'max_raw_csv_r15_error':max(errs),'constraints':'pass','legacy_recomputed_n':int(sum(r['recomputed_eligible'] for r in rows)),'legacy_named_but_ineligible':[r['date'] for r in rows if r['legacy_named14'] and not r['recomputed_eligible']],'eligible_not_legacy_named':[r['date'] for r in rows if r['recomputed_eligible'] and not r['legacy_named14']]}
 (ROOT/'results/validation.json').write_text(json.dumps(report,indent=2));print(report)
if __name__=='__main__':main()
