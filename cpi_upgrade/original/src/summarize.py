from net import ROOT
import pandas as pd,numpy as np
from scipy.stats import fisher_exact,ttest_1samp,spearmanr
from math import sqrt
SEED=20261011;BOOT=10000
RNG=np.random.default_rng(SEED)
PRICE_CACHE={}
def minute_drawdown(x,cost,exit_rule):
 equity=1.;peak=1.;dd=0.
 for _,e in x.sort_values('date').iterrows():
  d=e['date']
  if d not in PRICE_CACHE:
   df=pd.read_csv(ROOT/'data'/f'btc_{d}.csv.gz');df['ts']=pd.to_datetime(df.ts,utc=True);PRICE_CACHE[d]=df.set_index('ts')
  df=PRICE_CACHE[d];entry_t=pd.Timestamp(e.entry_utc);end_t=pd.Timestamp(e.baseline_exit_utc) if exit_rule=='btc_baseline_exit' else pd.Timestamp(e.t0_utc)+pd.Timedelta(minutes=int(e.horizon_min))
  px=df.loc[entry_t:end_t-pd.Timedelta(minutes=1),'close'].values
  path=equity*(1+e.direction*(px/e.entry_price-1)-cost/2)
  for val in path:
   peak=max(peak,float(val));dd=min(dd,float(val)/peak-1)
  equity*=1+float(e.net_return);peak=max(peak,equity);dd=min(dd,equity/peak-1)
 return dd
BINARY=['fade50_at_confirm','keep','new_extreme_touch','fade50_touch','fade100_touch','fade50_end','fade100_end','reverse5_touch','reverse5_end','gross_win','net_win']

def wilson(k,n):
 if n==0:return (np.nan,np.nan)
 z=1.959963984540054;den=1+z*z/n;mid=(k/n+z*z/(2*n))/den;half=z*sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/den
 return max(0,mid-half),min(1,mid+half)

def boot_ci(v,stat='mean'):
 v=np.asarray(v,dtype=float);v=v[np.isfinite(v)]
 if len(v)==0:return (np.nan,np.nan)
 b=v[RNG.integers(0,len(v),size=(BOOT,len(v)))];y=b.mean(axis=1) if stat=='mean' else np.median(b,axis=1)
 return tuple(np.quantile(y,[.025,.975]))

def summary(x):
 n=len(x);o={'n':n,'low_confidence_n_lt10':n<10}
 for k in BINARY:
  if k not in x:continue
  a=x[k].dropna();nn=len(a);count=int(a.sum());lo,hi=wilson(count,nn)
  o.update({k+'_n':nn,k+'_count':count,k+'_rate':count/nn if nn else np.nan,k+'_ci_low':lo,k+'_ci_high':hi})
 for k in ['first_return','release_return','gross_return','net_return','mfe','mae']:
  if k not in x:continue
  a=x[k].dropna().values
  if len(a):
   lo,hi=boot_ci(a);ml,mh=boot_ci(a,'median')
   o.update({k+'_mean':a.mean(),k+'_median':np.median(a),k+'_mean_ci_low':lo,k+'_mean_ci_high':hi,k+'_median_ci_low':ml,k+'_median_ci_high':mh})
 if 'net_return' in x and n:
  a=x.net_return.values;win=a[a>0];loss=a[a<0]
  o['payoff_ratio']=win.mean()/abs(loss.mean()) if len(win) and len(loss) else np.nan
  o['profit_factor']=win.sum()/abs(loss.sum()) if len(loss) else np.nan
  equity=np.cumprod(np.concatenate([[1.],1+a]));o['close_to_close_max_drawdown']=float((equity/np.maximum.accumulate(equity)-1).min());o['compound_return']=float(equity[-1]-1)
  o['mean_zero_ttest_p']=float(ttest_1samp(a,0).pvalue) if n>1 and a.std()>0 else np.nan
 return o

def bh(values):
 p=np.asarray(values,dtype=float);q=np.full_like(p,np.nan);ids=np.flatnonzero(np.isfinite(p));order=ids[np.argsort(p[ids])];m=len(order)
 if m:q[order]=np.minimum.accumulate((p[order]*m/np.arange(1,m+1))[::-1])[::-1].clip(0,1)
 return q

def group_table(x,keys,filters,label):
 rows=[]
 for threshold in filters:
  xx=x if threshold=='all' else x.loc[x.first_return.abs()>=float(threshold)]
  for vals,g in xx.groupby(keys,dropna=False,sort=True):
   if not isinstance(vals,tuple):vals=(vals,)
   rows.append({'table':label,'first_wave_filter':str(threshold),**dict(zip(keys,vals)),**summary(g.sort_values('date'))})
 return pd.DataFrame(rows)

def compare(a,b,col,name,binary=True,level='primary'):
 va=a[col].dropna().values;vb=b[col].dropna().values;na=len(va);nb=len(vb)
 row={'comparison':name,'metric':col,'n_a':na,'n_b':nb,'level':level,'effect_a_minus_b':np.mean(va)-np.mean(vb) if na and nb else np.nan}
 if not na or not nb:return {**row,'p_value':np.nan,'ci_low':np.nan,'ci_high':np.nan}
 if binary:
  ka=int(va.sum());kb=int(vb.sum());la,ua=wilson(ka,na);lb,ub=wilson(kb,nb);pa=ka/na;pb=kb/nb;delta=pa-pb
  row['ci_low']=delta-sqrt((pa-la)**2+(ub-pb)**2);row['ci_high']=delta+sqrt((ua-pa)**2+(pb-lb)**2);row['p_value']=fisher_exact([[ka,na-ka],[kb,nb-kb]]).pvalue
 else:
  bsa=va[RNG.integers(0,na,size=(BOOT,na))].mean(axis=1);bsb=vb[RNG.integers(0,nb,size=(BOOT,nb))].mean(axis=1);row['ci_low'],row['ci_high']=np.quantile(bsa-bsb,[.025,.975]);v=np.concatenate([va,vb]);observed=abs(va.mean()-vb.mean());cnt=0
  for _ in range(BOOT):
   shuffled=RNG.permutation(v);cnt+=abs(shuffled[:na].mean()-shuffled[na:].mean())>=observed-1e-15
  row['p_value']=(cnt+1)/(BOOT+1)
 return row

def main():
 p=pd.read_csv(ROOT/'results/event_paths.csv');x=p.loc[(p.confirm_min==15)&(p.status=='ok')].copy()
 tables={}
 tables['table_A_headline']=group_table(x,['headline_yoy_class','horizon_min'],['all',.003],'A')
 tables['table_A_combinations_yoy']=group_table(x,['combo_yoy','horizon_min'],['all',.003],'A-yoy')
 tables['table_A_combinations_mom']=group_table(x,['combo_mom','horizon_min'],['all',.003],'A-mom')
 for field in ['core_yoy','core_mom','headline_mom']:
  tables['table_A_'+field]=group_table(x,[field+'_class','horizon_min'],['all',.003],'A-'+field)
 tables['table_B_strict']=group_table(x.loc[x.headline_yoy_class=='cold'],['growth_strict','horizon_min'],['all',.003],'B-strict')
 tables['table_B_strict_up']=group_table(x.loc[(x.headline_yoy_class=='cold')&(x.first_return>=.003)],['growth_strict','horizon_min'],['all'],'B-strict-up')
 tables['table_B_snapshot_up']=group_table(x.loc[(x.headline_yoy_class=='cold')&(x.first_return>=.003)],['growth_snapshot','horizon_min'],['all'],'B-snapshot-up')
 tables['table_C_growth']=group_table(x.loc[x.headline_yoy_class=='cold'],['growth_snapshot','headline_yoy_size','horizon_min'],['all'],'C-growth')
 tables['table_B_snapshot']=group_table(x.loc[x.headline_yoy_class=='cold'],['growth_snapshot','horizon_min'],['all',.003],'B-snapshot')
 tables['table_C']=group_table(x,['headline_yoy_class','headline_yoy_size','horizon_min'],['all',.003],'C')
 tables['policy_stage']=group_table(x,['policy_stage','headline_yoy_class','horizon_min'],[.003],'policy')
 first=[]
 for c,g in p.loc[(p.status=='ok')&(p.horizon_min==30)].groupby('confirm_min'):
  for field in ['headline_yoy_class','core_yoy_class','headline_mom_class','core_mom_class','combo_mom','growth_strict','growth_snapshot']:
   for cl,gg in g.groupby(field,dropna=False):
    n=len(gg);row={'confirm_min':c,'group_field':field,'group':cl,'n':n,'first_return_mean':gg.first_return.mean(),'first_return_median':gg.first_return.median()}
    for k,mask in [('up',gg.first_return>0),('down',gg.first_return<0),('up_ge03',gg.first_return>=.003),('down_ge03',gg.first_return<=-.003),('quiet03',gg.first_return.abs()<.003)]:
     count=int(mask.sum());lo,hi=wilson(count,n);row.update({k+'_count':count,k+'_rate':count/n,k+'_ci_low':lo,k+'_ci_high':hi})
    first.append(row)
 tables['first_wave']=pd.DataFrame(first)
 # Small strategy menu, all fixed beforehand; no parameter ranking used for claims.
 strategies=[];trade_rows=[]
 for name,mask in [('momentum',x.first_return.abs()>=.003),('cpi_aligned',(x.first_return.abs()>=.003)&(((x.headline_yoy_class=='hot')&(x.direction==-1))|((x.headline_yoy_class=='cold')&(x.direction==1)))),('long_momentum',(x.first_return>=.003)),('short_momentum',(x.first_return<=-.003))]:
  for exit_rule in ['fixed','btc_baseline_exit']:
   xx=x.loc[mask].copy()
   if exit_rule=='btc_baseline_exit':
    xx['gross_return']=xx.baseline_exit_gross;xx['net_return']=xx.baseline_exit_net;xx['net_win']=(xx.net_return>0).astype(int);xx['gross_win']=(xx.gross_return>0).astype(int);xx['exit_price']=xx.baseline_exit_price;xx['mfe']=xx.baseline_exit_mfe;xx['mae']=xx.baseline_exit_mae
   for split,splmask in [('all',pd.Series(True,index=xx.index)),('explore_2019_2023',xx.year<=2023),('holdout_2024_2026',xx.year>=2024)]:
    for h,g in xx.loc[splmask].groupby('horizon_min'):
     for cost in [.0008,.0012,.0024,.004]:
      gg=g.copy();gg['net_return']=gg.gross_return-cost;gg['net_win']=(gg.net_return>0).astype(int);strategies.append({'strategy':name,'exit_rule':exit_rule,'split':split,'horizon_min':h,'roundtrip_cost_bps':round(cost*10000),'minute_close_max_drawdown':minute_drawdown(gg,cost,exit_rule),**summary(gg.sort_values('date'))})
   xx['strategy']=name;xx['exit_rule']=exit_rule;trade_rows.append(xx[['date','horizon_min','strategy','exit_rule','entry_utc','entry_price','exit_price','baseline_exit_utc','gross_return','net_return','net_win']])
 tables['table_F_strategies']=pd.DataFrame(strategies);tables['table_F_strategies']['q_all_strategy_tests']=bh(tables['table_F_strategies'].mean_zero_ttest_p)
 pd.concat(trade_rows).to_csv(ROOT/'results/trades.csv',index=False)
 sensitivity=[]
 for c,g in p.loc[p.status=='ok'].groupby('confirm_min'):
  for label,mask in [('abs02',g.first_return.abs()>=.002),('abs03',g.first_return.abs()>=.003),('abs05',g.first_return.abs()>=.005),('z1',g.z.abs()>=1),('z2',g.z.abs()>=2)]:
   for h,gg in g.loc[mask].groupby('horizon_min'):sensitivity.append({'confirm_min':c,'filter':label,'horizon_min':h,**summary(gg.sort_values('date'))})
 tables['sensitivity']=pd.DataFrame(sensitivity)
 tests=[]
 for h in [30,60,240,1440]:
  base=x.loc[x.horizon_min==h];active=base.loc[base.first_return.abs()>=.003]
  for stage in ['strict','snapshot']:
   col='growth_'+stage;aa=base.loc[(base.headline_yoy_class=='cold')&(base[col]=='stable')];bb=base.loc[(base.headline_yoy_class=='cold')&(base[col]=='deteriorating')]
   aa=aa.assign(first_up=(aa.first_return>0).astype(int));bb=bb.assign(first_up=(bb.first_return>0).astype(int))
   for metric in ['first_up','release_return']:
    tests.append(compare(aa,bb,metric,f'H1_{stage}_stable_minus_deteriorating_{h}m',metric=='first_up','primary' if stage=='strict' and h in [60,240] else 'exploratory'))
   aaa=aa.loc[aa.first_return>=.003];bbb=bb.loc[bb.first_return>=.003]
   for metric in ['keep','fade50_touch','fade100_touch','reverse5_touch','net_return']:
    tests.append(compare(aaa,bbb,metric,f'H1_{stage}_active_stable_minus_deteriorating_{h}m',metric!='net_return','primary' if stage=='strict' and h in [60,240] else 'exploratory'))
  a=active.loc[(active.headline_yoy_class=='hot')&(active.direction==-1)];b=active.loc[(active.headline_yoy_class=='cold')&(active.direction==1)]
  for metric in ['keep','fade50_touch','fade100_touch','reverse5_touch','net_return']:
   tests.append(compare(a,b,metric,f'H3_hot_down_minus_cold_up_{h}m',metric!='net_return','primary' if h in [60,240] else 'exploratory'))
  for cl in ['cold','hot']:
   a=base.loc[(base.headline_yoy_class==cl)&(base.headline_yoy_size=='large')];b=base.loc[(base.headline_yoy_class==cl)&(base.headline_yoy_size=='mild')]
   tests.append(compare(a,b,'release_return',f'C_{cl}_large_minus_mild_{h}m',False,'exploratory'))
 tests=pd.DataFrame(tests);tests['q_value']=np.nan
 for level in ['primary','exploratory']:
  mask=tests.level==level;tests.loc[mask,'q_value']=bh(tests.loc[mask,'p_value'].values)
 tables['hypothesis_tests']=tests
 ly=[]
 for year in sorted(x.year.unique()):
  for h,g in x.loc[(x.year!=year)&(x.first_return.abs()>=.003)].groupby('horizon_min'):ly.append({'removed_year':year,'horizon_min':h,**summary(g.sort_values('date'))})
 tables['leave_one_year_out']=pd.DataFrame(ly)
 # Year-block bootstrap protects against within-year dependence.
 cluster=[]
 for h,g in x.loc[x.first_return.abs()>=.003].groupby('horizon_min'):
  blocks=[gg.net_return.values for _,gg in g.groupby('year')];b=[]
  for _ in range(BOOT):b.append(np.concatenate([blocks[i] for i in RNG.integers(0,len(blocks),len(blocks))]).mean())
  lo,hi=np.quantile(b,[.025,.975]);cluster.append({'horizon_min':h,'n':len(g),'year_blocks':len(blocks),'net_mean':g.net_return.mean(),'ci_low':lo,'ci_high':hi})
 tables['year_cluster_bootstrap']=pd.DataFrame(cluster)
 # Neither success counts nor probabilities are manufactured for absent cross assets.
 tables['table_D_cross_asset']=pd.DataFrame([{'state':s,'n':0,'status':'not_verified_missing_2Y_ZT_NQ','missing_dates_file':'cross_asset_missing.csv'} for s in ['2Y_down_NQ_up','2Y_down_NQ_down','2Y_up_NQ_down','2Y_up_NQ_up']])
 tables['table_E_rate_reversal']=pd.DataFrame([{'state':s,'n':0,'status':'not_verified_missing_high_frequency_rate_path'} for s in ['persists','reverses','ambiguous']])
 pd.DataFrame([{'date':d,'2Y':'missing','ZT':'missing','NQ':'missing','DXY':'missing','fomc_futures_snapshot':'missing'} for d in sorted(x.date.unique())]).to_csv(ROOT/'results/cross_asset_missing.csv',index=False)
 for name,t in tables.items():t.to_csv(ROOT/'results'/f'{name}.csv',index=False,float_format='%.12g')
 print('tables', {k:len(v) for k,v in tables.items()})
 print(tables['table_A_headline'].loc[tables['table_A_headline'].first_wave_filter=='0.003',['headline_yoy_class','horizon_min','n','keep_rate','fade100_touch_rate','reverse5_touch_rate','net_win_rate','net_return_mean']].to_string(index=False))
 print(tables['table_F_strategies'].loc[(tables['table_F_strategies'].strategy=='momentum')&(tables['table_F_strategies'].exit_rule=='fixed')&(tables['table_F_strategies'].roundtrip_cost_bps==24),['split','horizon_min','n','net_win_rate','net_return_mean','net_return_mean_ci_low','net_return_mean_ci_high']].to_string(index=False))
if __name__=='__main__':main()
