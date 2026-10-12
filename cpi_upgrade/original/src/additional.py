from net import ROOT
from summarize import summary,boot_ci,bh,wilson
import numpy as np,pandas as pd,json
from scipy.stats import t as tdist,ttest_1samp,binomtest
from clean import occurrences

def main():
 x=pd.read_csv(ROOT/'results/event_paths.csv');x=x[(x.confirm_min==15)&(x.status=='ok')]
 # Known simultaneous releases; coverage is restricted to this explicit source universe.
 raw=json.loads((ROOT/'raw/consensus.json').read_text());events=pd.read_csv(ROOT/'data/events_cpi.csv');co=[]
 fed=pd.DataFrame(occurrences('investing_fomc.html'));fed['ts']=pd.to_datetime(fed.occurrence_time,utc=True)
 for _,e in events.iterrows():
  names=[]
  for s in raw['series']:
   if s['eventId'] in [733,736,168]:continue
   for r in s['occurrences']:
    if r.get('actual') is not None and r.get('occurrenceTime')==e.t0_utc.replace('+00:00','Z'):names.append(s['label'])
  t0=pd.Timestamp(e.t0_utc);f=fed[(fed.ts>t0)&(fed.ts<=t0+pd.Timedelta(hours=24))&fed.actual.notna()]
  co.append({'date':e['date'],'other_0830_known':';'.join(sorted(set(names))),'other_0830_known_n':len(set(names)),'coverage':'14-series public snapshot; not exhaustive; BLS Real Earnings derived from CPI excluded','fomc_release_within_24h':int(len(f)>0),'fomc_later_release_utc':';'.join(z.isoformat() for z in f.ts),'fomc_timing_status':'historical release record for confound audit, not future rate expectation or certified pre-release schedule vintage'})
 c=pd.DataFrame(co);c.to_csv(ROOT/'results/simultaneous_releases.csv',index=False)
 xx=x.merge(c,on='date');sim=[]
 for h,g in xx[(xx.first_return.abs()>=.003)&(xx.other_0830_known_n==0)].groupby('horizon_min'):sim.append({'horizon_min':h,**summary(g.sort_values('date'))})
 pd.DataFrame(sim).to_csv(ROOT/'results/exclude_known_simultaneous.csv',index=False)
 sim=[]
 for h,g in xx[(xx.first_return.abs()>=.003)&(xx.other_0830_known_n==0)&(xx.fomc_release_within_24h==0)].groupby('horizon_min'):sim.append({'horizon_min':h,**summary(g.sort_values('date'))})
 pd.DataFrame(sim).to_csv(ROOT/'results/exclude_simultaneous_and_fomc.csv',index=False)
 # Exploratory interaction, HC3 standard errors; growth snapshots retain a vintage caveat.
 rows=[]
 for regime in ['growth_strict','growth_snapshot']:
  for h in [30,60,240]:
   g=x[(x.horizon_min==h)&(x.headline_yoy_class=='cold')&(x[regime]!='unclassified')].copy()
   for target in ['first_return','release_return']:
    a=g.headline_yoy_surprise_pp.abs().values;b=(g[regime]=='deteriorating').astype(float).values;X=np.column_stack([np.ones(len(g)),a,b,a*b]);y=g[target].values
    if len(g)<=4 or np.linalg.matrix_rank(X)<4:
     rows.append({'growth_spec':regime,'horizon_min':h,'target':target,'n':len(g),'status':'rank_deficient_or_insufficient'});continue
    inv=np.linalg.inv(X.T@X);beta=inv@X.T@y;res=y-X@beta;lever=np.sum((X@inv)*X,axis=1);omega=(res/(1-lever))**2;cov=inv@(X.T@(omega[:,None]*X))@inv;se=np.sqrt(np.diag(cov));crit=tdist.ppf(.975,len(y)-4)
    for k,name in enumerate(['intercept','abs_surprise','growth_bad','surprise_growth_interaction']):
     rows.append({'growth_spec':regime,'horizon_min':h,'target':target,'n':len(y),'term':name,'coefficient':beta[k],'ci_low':beta[k]-crit*se[k],'ci_high':beta[k]+crit*se[k],'p_value':2*tdist.sf(abs(beta[k]/se[k]),len(y)-4),'status':'exploratory_HC3; no causal interpretation'})
 out=pd.DataFrame(rows);out['q_value']=bh(out.p_value);out.to_csv(ROOT/'results/surprise_growth_interaction.csv',index=False)
 # Paired exit-rule comparison, BTC baseline rule; this is not a rate exit.
 pairs=[]
 for split,mask in [('all',x.year>=2019),('explore_2019_2023',x.year<=2023),('holdout_2024_2026',x.year>=2024)]:
  for h,g in x[mask&(x.first_return.abs()>=.003)].groupby('horizon_min'):
   dif=g.baseline_exit_net-g.net_return;lo,hi=boot_ci(dif);pairs.append({'split':split,'horizon_min':h,'n':len(g),'net_improvement_mean':dif.mean(),'ci_low':lo,'ci_high':hi,'p_value':ttest_1samp(dif,0).pvalue if dif.std()>0 else np.nan,'exit_trigger_count':g.baseline_exit_min.notna().sum()})
 pairs=pd.DataFrame(pairs);pairs['q_value']=bh(pairs.p_value);pairs.to_csv(ROOT/'results/paired_btc_exit_test.csv',index=False)
 # Conditional hot/cold aligned first wave for H3 and paired before/after cash-open comparison.
 aligned=x[(x.first_return.abs()>=.003)&(((x.headline_yoy_class=='hot')&(x.direction==-1))|((x.headline_yoy_class=='cold')&(x.direction==1)))];rows=[]
 for (cl,h),g in aligned.groupby(['headline_yoy_class','horizon_min']):rows.append({'cpi_class':cl,'horizon_min':h,**summary(g.sort_values('date'))})
 pd.DataFrame(rows).to_csv(ROOT/'results/H3_aligned_details.csv',index=False)
 one=x[(x.first_return.abs()>=.003)&(x.horizon_min==60)].set_index('date');four=x[(x.first_return.abs()>=.003)&(x.horizon_min==240)].set_index('date');a=one.keep;b=four.keep.reindex(one.index);lost=int(((a==1)&(b==0)).sum());gained=int(((a==0)&(b==1)).sum())
 pd.DataFrame([{'n_pairs':len(a),'keep_60m_count':int(a.sum()),'keep_240m_count':int(b.sum()),'lost':lost,'gained':gained,'keep_change_pp':100*(b.mean()-a.mean()),'mcnemar_exact_p':binomtest(min(lost,gained),lost+gained,.5).pvalue}]).to_csv(ROOT/'results/cash_open_comparison.csv',index=False)
 # Crossvenue strategy comparison using exactly the same Binance-selected event set.
 cb=pd.read_csv(ROOT/'results/coinbase_event_paths.csv');btcsel=x[(x.first_return.abs()>=.003)&(x.horizon_min.isin([30,60,240]))][['date','horizon_min']];cv=cb.merge(btcsel,on=['date','horizon_min']);cv=cv[cv.status=='ok'];rows=[]
 for h,g in cv.groupby('horizon_min'):rows.append({'venue':'Coinbase BTC-USD','horizon_min':h,'selection':'same events chosen from Binance','entry_cost_assumption_bps':24,**summary(g.sort_values('date'))})
 pd.DataFrame(rows).to_csv(ROOT/'results/crossvenue_strategy.csv',index=False)
 # Event database includes explicit unknown cross-asset fields and known simultaneous records.
 w=pd.read_csv(ROOT/'results/table_G_events.csv').drop(columns=list(c.columns[1:]),errors='ignore').merge(c,on='date')
 for asset in ['2Y','ZT','NQ','DXY']:
  for h in [15,30,60,240]:w[f'{asset}_return_{h}m']=np.nan
 w['cross_asset_status']='not_obtained';w.to_csv(ROOT/'results/table_G_events.csv',index=False,float_format='%.12g')
 print('additional analyses complete')
if __name__=='__main__':main()
