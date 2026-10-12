from clean import occurrences
from net import ROOT
import pandas as pd,numpy as np
from datetime import datetime,timedelta

def vintage(d,sid):
 p=ROOT/'raw/vintages'/f'{d}_{sid}.csv'
 vd=(datetime.fromisoformat(d)-timedelta(days=1)).strftime('%Y%m%d')
 if not p.exists():raise ValueError('missing file')
 x=pd.read_csv(p)
 if list(x.columns)!=['observation_date',f'{sid}_{vd}']:raise ValueError('vintage header mismatch')
 x.columns=['month','value'];x.value=pd.to_numeric(x.value,errors='coerce');x=x.dropna().sort_values('month')
 if x.empty:raise ValueError('no observations')
 if (pd.Timestamp(d)-(pd.Timestamp(x.iloc[-1]['month'])+pd.offsets.MonthEnd(0))).days>95:raise ValueError('stale >95 days')
 return x

def classify(flags):
 known=[int(x) for x in flags if pd.notna(x)]
 if len(known)<2:return 'unclassified'
 bad=sum(known);unknown=3-len(known)
 if bad>=2:return 'deteriorating'
 if bad+unknown<2:return 'stable'
 return 'unclassified'

def monthly_series(x):
 s=x.copy();s['period']=pd.to_datetime(s.month).dt.to_period('M')
 if s.period.duplicated().any():raise ValueError('Duplicate monthly observations')
 return s.set_index('period').value

def main():
 es=pd.read_csv(ROOT/'data/events_cpi.csv')
 ism=pd.DataFrame(occurrences('investing_ism.html'))
 ism['ts']=pd.to_datetime(ism.occurrence_time,utc=True);ism=ism.sort_values('ts');ism=ism.loc[ism.actual.notna()]
 fed=pd.DataFrame(occurrences('investing_fomc.html'));fed['ts']=pd.to_datetime(fed.occurrence_time,utc=True);fed=fed.sort_values('ts');fed=fed.loc[fed.actual.notna()]
 rows=[];audit=[];windows=[]
 for _,e in es.iterrows():
  d=e['date'];row={'date':d,'employment_bad':np.nan,'consumption_bad':np.nan,'ism_bad_release_snapshot':np.nan,'ism_bad_strict':np.nan}
  vs={}
  for sid in ['UNRATE','PAYEMS','PCEC96','DFEDTARU']:
   try:
    x=vintage(d,sid);vs[sid]=x;row[sid+'_last_observation']=x.iloc[-1]['month'];row[sid+'_latest']=x.iloc[-1].value
    audit.append({'date':d,'series':sid,'status':'verified_vintage_header','vintage':(datetime.fromisoformat(d)-timedelta(days=1)).date().isoformat(),'last_observation':x.iloc[-1]['month']})
   except Exception as er:audit.append({'date':d,'series':sid,'status':str(er)})
  u=vs.get('UNRATE');p=vs.get('PAYEMS');c=vs.get('PCEC96')
  if u is not None and p is not None and len(u)>=4 and len(p)>=7:
   us=monthly_series(u);ps=monthly_series(p);ref=us.index[-1]-3;uv=us.get(ref,np.nan);ud=round(us.iloc[-1]-uv,3) if pd.notna(uv) else np.nan
   needed=pd.period_range(ps.index[-1]-6,ps.index[-1],freq='M');pv=ps.reindex(needed);changes=pv.diff().iloc[1:]
   n3=changes.iloc[-3:].mean() if changes.iloc[-3:].notna().all() else np.nan;n6=changes.mean() if changes.notna().all() else np.nan
   ub=int(ud>=.2) if pd.notna(ud) else np.nan;pb=int(n3<n6) if pd.notna(n3) and pd.notna(n6) else np.nan
   eb=1 if ub==1 or pb==1 else 0 if pd.notna(ub) and pd.notna(pb) else np.nan
   row.update({'unrate_3m_reference_month':str(ref),'unrate_3m_change_pp':ud,'unrate_bad':ub,'payroll_bad':pb,'payroll_3m_average_thousands':n3,'payroll_6m_average_thousands':n6,'payroll_last3_changes_thousands':'/'.join(str(round(a,1)) if pd.notna(a) else 'missing' for a in changes.iloc[-3:]),'employment_bad':eb})
   windows.append({'date':d,'series':'UNRATE','latest_month':str(us.index[-1]),'reference_month':str(ref),'missing_required_months':str(ref) if pd.isna(uv) else '', 'status':'missing_3m_reference' if pd.isna(uv) else 'exact_calendar_3m'})
   windows.append({'date':d,'series':'PAYEMS','latest_month':str(ps.index[-1]),'reference_month':str(needed[0]),'missing_required_months':';'.join(str(m) for m in needed[pv.isna()]),'status':'exact_calendar_6m' if pv.notna().all() else 'missing_month_in_changes'})
  if c is not None and len(c)>=4:
   cs=monthly_series(c);ref=cs.index[-1]-3;v=cs.get(ref,np.nan);mom3=cs.iloc[-1]/v-1 if pd.notna(v) else np.nan;row['real_pce_3m_return']=mom3;row['consumption_bad']=int(mom3<=0) if pd.notna(mom3) else np.nan
   windows.append({'date':d,'series':'PCEC96','latest_month':str(cs.index[-1]),'reference_month':str(ref),'missing_required_months':str(ref) if pd.isna(v) else '', 'status':'exact_calendar_3m' if pd.notna(v) else 'missing_3m_reference'})
  im=ism.loc[ism.ts<pd.Timestamp(e.t0_utc)].tail(6)
  if len(im)==6:
   avg3=im.actual.iloc[-3:].mean();prev3=im.actual.iloc[:3].mean();row.update({'ism_latest_release':str(im.ts.iloc[-1]),'ism_latest':im.actual.iloc[-1],'ism_3m_average':avg3,'ism_previous3m_average':prev3,'ism_bad_release_snapshot':int(avg3<50 and avg3<prev3),'ism_pit_status':'release-specific actual; original vintage not independently archived'})
  row['growth_strict']=classify([row['employment_bad'],row['consumption_bad'],row['ism_bad_strict']])
  row['growth_snapshot']=classify([row['employment_bad'],row['consumption_bad'],row['ism_bad_release_snapshot']])
  fm=fed.loc[fed.ts<pd.Timestamp(e.t0_utc)].tail(1)
  if len(fm):
   fr=fm.iloc[0];row['last_fomc_date']=fr.ts.date().isoformat();row['last_fomc_actual_upper']=fr.actual;row['last_fomc_forecast_upper']=fr.get('forecast',np.nan);prev=fr.get('previous',np.nan)
   row['policy_stage']='hiking' if fr.actual>prev else 'cutting' if fr.actual<prev else 'pause' if pd.notna(prev) else 'unclassified'
   row['fomc_matches_vintage']=bool('DFEDTARU' in vs and abs(fr.actual-vs['DFEDTARU'].iloc[-1].value)<0.001)
  row['future_fomc_market_expectation']='missing historical futures/snapshot'
  row['pandemic_crisis']=int('2020-03-01'<=d<='2020-06-30');row['high_inflation']=int(e.headline_yoy_actual>=4);row['rapid_hiking']=int('2022-03-16'<=d<='2022-12-31')
  rows.append(row)
 out=pd.DataFrame(rows);out.to_csv(ROOT/'data/growth.csv',index=False);pd.DataFrame(audit).to_csv(ROOT/'results/growth_audit.csv',index=False)
 pd.DataFrame(windows).to_csv(ROOT/'results/growth_calendar_window_audit.csv',index=False)
 print('growth_strict',out.growth_strict.value_counts().to_dict(),'growth_snapshot',out.growth_snapshot.value_counts().to_dict());print('vintages',pd.DataFrame(audit).status.value_counts().to_dict());print('fomc mismatch',out.loc[~out.fomc_matches_vintage.fillna(False),['date','last_fomc_actual_upper','DFEDTARU_latest']].to_dict('records'))
if __name__=='__main__':main()
