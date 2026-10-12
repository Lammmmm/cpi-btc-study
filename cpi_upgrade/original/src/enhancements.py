"""Supplementary audits and sensitivity checks. Never changes the fixed main spec."""
from net import ROOT
from summarize import summary,compare,bh,boot_ci,wilson
import pandas as pd,numpy as np,hashlib,json,gzip
from lxml import html
from scipy.stats import fisher_exact

def main():
 x=pd.read_csv(ROOT/'results/event_paths.csv');x=x[(x.confirm_min==15)&(x.status=='ok')].copy()
 # Audit primary notices locally; ship factual snapshots, not full copyrighted articles.
 fa=[];fee_facts=[];frozen=ROOT/'data/fee_schedule_facts.json'
 logs=[json.loads(line) for line in (ROOT/'raw/download_log.jsonl').read_text().splitlines()];byfile={r.get('file'):r for r in logs if r.get('file')}
 for name,terms in [('zero_fee_start',['2022-07-08','14:00','BTC/USDT']),('zero_fee_end',['2023-03-22','BTC/USDT','Standard']),('spot_fee_faq',['0.1%'])]:
  original=ROOT/'raw/fees'/f'{name}.html';keyfacts={'pair':'BTCUSDT',**({'effective_start_utc':'2022-07-08T14:00:00Z','maker_fee':0,'taker_fee':0} if name=='zero_fee_start' else {'effective_end_utc':'2023-03-22T00:00:00Z','fee_after_end':'standard user VIP schedule'} if name=='zero_fee_end' else {'standard_reference_single_side_fee':.001,'historical_account_fee_certified':False})}
  if original.exists():
   b=original.read_bytes();encoded=b.startswith(b'\x1f\x8b');decoded=gzip.decompress(b) if encoded else b;text=html.fromstring(decoded).text_content()
   checks={term:term in text for term in terms};assert all(checks.values()),f'Fee source payload lacks expected terms: {name} {checks}'
   log=byfile.get(f'raw/fees/{name}.html',{});fact={'source_name':name,'url':log.get('url'),'acquired_utc':log.get('utc'),'original_http_sha256':hashlib.sha256(b).hexdigest(),'http_body_gzip_encoded':encoded,'key_facts':keyfacts}
  else:
   stored=json.loads(frozen.read_text());fact=next(s for s in stored['sources'] if s['source_name']==name);assert fact['key_facts']==keyfacts;encoded=fact['http_body_gzip_encoded'];checks={'frozen_facts_match_verified_primary_notice':True}
  fee_facts.append(fact);fa.append({'source_name':name,'source_url':fact['url'],'original_http_sha256':fact['original_http_sha256'],'http_body_gzip_encoded':encoded,'required_facts_verified':json.dumps(checks),'status':'verified_primary_notice_factual_snapshot'})
 frozen.write_text(json.dumps({'sources':fee_facts,'scope':'public factual dates, pair and fee rules; original article prose omitted; standard rate is a scenario'},ensure_ascii=False,indent=2))
 pd.DataFrame(fa).to_csv(ROOT/'results/fee_schedule_audit.csv',index=False)
 # Public BTCUSDT fee promotion, known historical dates; 4bp slippage remains assumed.
 x['zero_fee_promotion']=x.date.between('2022-07-08','2023-03-21')
 x['historical_fee_scenario_cost_bps']=np.where(x.zero_fee_promotion,4,24)
 x['historical_fee_scenario_net']=x.gross_return-x.historical_fee_scenario_cost_bps/10000
 fee_rows=[]
 for strategy,mask in [('momentum',x.first_return.abs()>=.003),('long_momentum',x.first_return>=.003),('short_momentum',x.first_return<=-.003),('cpi_aligned',(x.first_return.abs()>=.003)&(((x.headline_yoy_class=='cold')&(x.direction==1))|((x.headline_yoy_class=='hot')&(x.direction==-1))))]:
  for split,part in [('all',x.year>=2019),('explore_2019_2023',x.year<=2023),('holdout_2024_2026',x.year>=2024)]:
   for h,g in x[mask&part].groupby('horizon_min'):
    gg=g.copy();gg['net_return']=gg.historical_fee_scenario_net;gg['net_win']=(gg.net_return>0).astype(int)
    fee_rows.append({'strategy':strategy,'split':split,'horizon_min':h,'zero_fee_events':int(g.zero_fee_promotion.sum()),'cost':'4bp during verified BTCUSDT zero-fee promotion; 24bp otherwise; VIP0 scenario',**summary(gg.sort_values('date'))})
 ft=pd.DataFrame(fee_rows);ft['q_explore_fee_tests']=bh(ft.mean_zero_ttest_p);ft.to_csv(ROOT/'results/historical_fee_scenario.csv',index=False,float_format='%.12g')
 x[['date','horizon_min','direction','gross_return','zero_fee_promotion','historical_fee_scenario_cost_bps','historical_fee_scenario_net']].to_csv(ROOT/'results/historical_fee_event_returns.csv',index=False)
 # Headline/Core/energy diagnostics; descriptive data, not demand-causation labels.
 component=[]
 cold=x[x.headline_yoy_class=='cold'].copy()
 cold['energy_direction']=np.where(cold.energy_mom_actual<0,'energy_mom_down',np.where(cold.energy_mom_actual>=0,'energy_mom_nonnegative','missing'))
 for (core,energy,h),g in cold.groupby(['core_mom_class','energy_direction','horizon_min']):component.append({'core_mom_class':core,'energy_direction':energy,'horizon_min':h,**summary(g.sort_values('date'))})
 ct=pd.DataFrame(component);ct['q_explore_component_tests']=bh(ct.mean_zero_ttest_p);ct.to_csv(ROOT/'results/cold_components.csv',index=False)
 regimes=[]
 for flag in ['pandemic_crisis','high_inflation','rapid_hiking']:
  for (state,cl,h),g in x[x.first_return.abs()>=.003].groupby([flag,'headline_yoy_class','horizon_min']):regimes.append({'regime_flag':flag,'flag_value':state,'cpi_class':cl,'horizon_min':h,**summary(g.sort_values('date'))})
 rt=pd.DataFrame(regimes);rt['q_explore_regime_tests']=bh(rt.mean_zero_ttest_p);rt.to_csv(ROOT/'results/regime_sensitivity.csv',index=False,float_format='%.12g')
 # Optimistic 0-minute and slower 2-minute execution around the fixed 1-minute lag.
 lagrows=[];cache={}
 for lag in [0,1,2]:
  for h,g in x[x.first_return.abs()>=.003].groupby('horizon_min'):
   rr=[]
   for _,e in g.iterrows():
    d=e['date']
    if d not in cache:
     z=pd.read_csv(ROOT/'data'/f'btc_{d}.csv.gz');z['ts']=pd.to_datetime(z.ts,utc=True);cache[d]=z.set_index('ts')
    entry=float(cache[d].loc[pd.Timestamp(e.t0_utc)+pd.Timedelta(minutes=15+lag),'open']);gross=e.direction*(e.exit_price/entry-1)
    rr.append({'date':d,'gross_return':gross,'net_return':gross-.0024,'net_win':int(gross>.0024)})
   stats=summary(pd.DataFrame(rr).sort_values('date'))
   if lag==1:
    primary=pd.read_csv(ROOT/'results/table_F_strategies.csv');primary=primary[(primary.strategy=='momentum')&(primary.exit_rule=='fixed')&(primary.split=='all')&(primary.roundtrip_cost_bps==24)&(primary.horizon_min==h)].iloc[0]
    # Same estimator/cohort: retain main table's bootstrap draw, not a second MC interval.
    stats.update({k:primary[k] for k in stats if k in primary.index})
   lagrows.append({'execution_lag_min':lag,'entry_min_since_cpi':15+lag,'horizon_min':h,**stats})
 lt=pd.DataFrame(lagrows);lt['q_explore_latency_tests']=bh(lt.mean_zero_ttest_p);lt.to_csv(ROOT/'results/execution_latency_sensitivity.csv',index=False,float_format='%.12g')
 # Surprise magnitude sensitivity: 0.2pp main and 0.3pp exploratory.
 rows=[]
 for cut in [.2,.3]:
  y=x.copy();y['surprise_bin']=np.where(y.headline_yoy_surprise_pp.abs()>=cut,'large',np.where(y.headline_yoy_surprise_pp!=0,'mild','inline'))
  for (cl,level,h),g in y.groupby(['headline_yoy_class','surprise_bin','horizon_min']):rows.append({'large_threshold_pp':cut,'cpi_class':cl,'size':level,'horizon_min':h,**summary(g.sort_values('date'))})
 pd.DataFrame(rows).to_csv(ROOT/'results/surprise_threshold_sensitivity.csv',index=False)
 # Pairwise hot/cold/inline first direction and unconditional horizon differences.
 tests=[]
 for ca,cb in [('cold','hot'),('cold','inline'),('hot','inline')]:
  for h in [30,60,240,1440]:
   a=x[(x.headline_yoy_class==ca)&(x.horizon_min==h)].copy();b=x[(x.headline_yoy_class==cb)&(x.horizon_min==h)].copy()
   tests.append(compare(a,b,'release_return',f'A_{ca}_minus_{cb}_{h}m',False,'exploratory'))
   if h==30:
    a['first_up']=(a.first_return>0).astype(int);b['first_up']=(b.first_return>0).astype(int)
    tests.append(compare(a,b,'first_up',f'A_{ca}_minus_{cb}_first_up',True,'exploratory'))
 tests=pd.DataFrame(tests);tests['q_value']=bh(tests.p_value);tests.to_csv(ROOT/'results/table_A_tests.csv',index=False)
 # Old selected rule can have positive sample means despite low win rate; report it fairly.
 legacy=pd.read_csv(ROOT/'results/legacy_audit.csv');legacy=legacy[legacy.recomputed_eligible];ls=[]
 for split,mask in [('all',legacy.date>='2019'),('explore_2019_2023',legacy.date<'2024'),('holdout_2024_2026',legacy.date>='2024')]:
  for h in [30,60,240]:
   g=legacy[mask].copy();g['net_return']=g[f'net_return_entry11_{h}m'];g['net_win']=(g.net_return>0).astype(int)
   ls.append({'split':split,'horizon_min':h,**summary(g)})
 ls=pd.DataFrame(ls);ls['q_value']=bh(ls.mean_zero_ttest_p);ls.to_csv(ROOT/'results/legacy_strategy_statistics.csv',index=False,float_format='%.12g')
 # Published official checksums, not just locally generated hashes.
 rows=[]
 for p in sorted((ROOT/'raw/btc').glob('*.zip')):
  q=p.with_name(p.name+'.CHECKSUM');expected=q.read_text().split()[0] if q.exists() else None;got=hashlib.sha256(p.read_bytes()).hexdigest();rows.append({'file':str(p.relative_to(ROOT)),'official_sha256':expected,'computed_sha256':got,'matches':got==expected})
 assert len(rows)==184 and all(r['matches'] for r in rows)
 pd.DataFrame(rows).to_csv(ROOT/'results/source_checksum_audit.csv',index=False)
 # Explicit date-level missingness. All untouched cross-asset gaps are separate.
 missing=[]
 for _,e in pd.read_csv(ROOT/'data/events_cpi.csv').iterrows():
  for f in ['headline_yoy','headline_mom','core_yoy','core_mom']:
   for suffix in ['actual','forecast']:
    if pd.isna(e[f+'_'+suffix]):missing.append({'date':e['date'],'field':f+'_'+suffix,'reason':'BLS October 2025 reference CPI not published; November MoM unavailable','effect':'excluded from this field only; YoY/BTC retained'})
 for _,e in pd.read_csv(ROOT/'results/btc_audit.csv').iterrows():
  if e.missing_minutes:missing.append({'date':e['date'],'field':'BTC_24h_path','reason':f'{int(e.missing_minutes)} source minutes absent; see btc_audit.csv UTC list','effect':'24h excluded for every confirmation; 4h and shorter retained'})
 for _,e in pd.read_csv(ROOT/'results/growth_audit.csv').iterrows():
  if e.status!='verified_vintage_header':missing.append({'date':e['date'],'field':e.series,'reason':e.status,'effect':'growth uses logical bounds; no forward-fill'})
 for _,e in pd.read_csv(ROOT/'results/growth_calendar_window_audit.csv').iterrows():
  if e.status.startswith('missing'):missing.append({'date':e['date'],'field':e.series+'_calendar_window','reason':e.status+'; required '+str(e.missing_required_months),'effect':'unknown sub-signal, employment OR uses logical bounds; no nonadjacent-month replacement'})
 for _,e in pd.read_csv(ROOT/'data/growth.csv').iterrows():
  missing.append({'date':e['date'],'field':'ISM_strict_original_vintage','reason':'release-specific calendar actual, original vintage not fully independently certified','effect':'strict growth only bounded from employment/PCE; expanded snapshot sensitivity separately'})
  missing.append({'date':e['date'],'field':'future_FOMC_market_expectations','reason':'no historical futures probability/snapshot authorization','effect':'no policy expectation conditioned result'})
 pd.DataFrame(missing).to_csv(ROOT/'results/missing_data.csv',index=False)
 # First-direction denominators for H1, including quiet positive moves and all confirmations.
 allpaths=pd.read_csv(ROOT/'results/event_paths.csv');allpaths=allpaths[(allpaths.status=='ok')&(allpaths.horizon_min==30)&(allpaths.headline_yoy_class=='cold')];h1=[]
 for spec in ['strict','snapshot']:
  for (c,state),g in allpaths.groupby(['confirm_min','growth_'+spec]):
   row={'growth_spec':spec,'growth_state':state,'confirm_min':c,'n':len(g),'first_return_mean':g.first_return.mean(),'first_return_median':g.first_return.median()}
   for name,mask in [('first_up',g.first_return>0),('first_down',g.first_return<0),('first_up_ge03',g.first_return>=.003),('first_down_le03',g.first_return<=-.003),('quiet03',g.first_return.abs()<.003)]:
    k=int(mask.sum());lo,hi=wilson(k,len(g));row.update({name+'_count':k,name+'_rate':k/len(g),name+'_ci_low':lo,name+'_ci_high':hi})
   h1.append(row)
 pd.DataFrame(h1).to_csv(ROOT/'results/H1_first_wave.csv',index=False,float_format='%.12g')
 w=pd.read_csv(ROOT/'results/table_G_events.csv')
 f=x[x.horizon_min==30][['date','zero_fee_promotion','historical_fee_scenario_cost_bps']]
 w=w.drop(columns=['zero_fee_promotion','historical_fee_scenario_cost_bps'],errors='ignore').merge(f,on='date')
 for h in [30,60,240,1440]:
  name=f'historical_fee_scenario_net_{h}m';w=w.drop(columns=[name],errors='ignore').merge(x[x.horizon_min==h][['date','historical_fee_scenario_net']].rename(columns={'historical_fee_scenario_net':name}),on='date',how='left')
 w.to_csv(ROOT/'results/table_G_events.csv',index=False,float_format='%.12g')
 print('enhancements complete; official checksum audit 184/184')

if __name__=='__main__':main()
