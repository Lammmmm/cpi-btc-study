from net import ROOT
import pandas as pd,numpy as np,json
HORIZONS=[30,60,240,1440]

def calc(df,t0,c,h):
 # Bar timestamp denotes its start; confirmation close belongs to c-1 minute.
 expect=pd.date_range(t0-pd.Timedelta(minutes=1),t0+pd.Timedelta(minutes=h),freq='min')
 if len(expect.difference(df.index)):return {'status':'missing_in_required_window'}
 x=df.loc[expect];p0=float(x.loc[t0-pd.Timedelta(minutes=1),'close']);pc=float(x.loc[t0+pd.Timedelta(minutes=c-1),'close']);r=pc/p0-1;s=int(np.sign(r))
 if s==0:return {'status':'zero_first_wave','p0':p0,'first_return':r}
 preidx=pd.date_range(t0-pd.Timedelta(minutes=60),t0-pd.Timedelta(minutes=1),freq='min')
 sigma=np.nan
 if not len(preidx.difference(df.index)):
  sigma=float(np.log(df.loc[preidx,'close']).diff().dropna().std(ddof=1)*np.sqrt(c))
 first=x.loc[t0:t0+pd.Timedelta(minutes=c-1)];after=x.loc[t0+pd.Timedelta(minutes=c):t0+pd.Timedelta(minutes=h-1)]
 extreme=float(first.high.max() if s==1 else first.low.min());eamp=s*(extreme-p0)
 end=float(x.loc[t0+pd.Timedelta(minutes=h-1),'close']);worst=float(after.low.min() if s==1 else after.high.max());best=float(after.high.max() if s==1 else after.low.min())
 entry_t=t0+pd.Timedelta(minutes=c+1);entry=float(x.loc[entry_t,'open']);exit=float(x.loc[t0+pd.Timedelta(minutes=h),'open']);gross=s*(exit/entry-1)
 trade=x.loc[entry_t:t0+pd.Timedelta(minutes=h-1)]
 trade_prices=np.concatenate([trade.high.values,trade.low.values,np.array([exit])]);signed=s*(trade_prices/entry-1);mfe=max(0.,float(signed.max()));mae=min(0.,float(signed.min()))
 close5=[]
 for m in range(c+5,h+1,5):close5.append((m,float(x.loc[t0+pd.Timedelta(minutes=m-1),'close'])))
 revm=next((m for m,p in close5 if s*(p-p0)<0),None)
 continuous=[];last=p0
 for m in range(5,c+1,5):
  p=float(x.loc[t0+pd.Timedelta(minutes=m-1),'close']);continuous.append(s*(p-last)>0);last=p
 # BTC-baseline exit is separate from the missing rate-reversal rule.
 stop_m=next((m for m,p in close5 if m+1<h and s*(p-p0)<0),None)
 stop_exit=float(x.loc[t0+pd.Timedelta(minutes=stop_m+1),'open']) if stop_m else exit
 stop_time=t0+pd.Timedelta(minutes=stop_m+1) if stop_m else t0+pd.Timedelta(minutes=h)
 stop_trade=x.loc[entry_t:stop_time-pd.Timedelta(minutes=1)]
 stop_signed=s*(np.concatenate([stop_trade.high.values,stop_trade.low.values,[stop_exit]])/entry-1)
 out={'status':'ok','p0':p0,'confirm_price':pc,'first_return':r,'direction':s,'fade50_at_confirm':int(s*(pc-p0)<=eamp*.5),'first_extreme':extreme,'first_continuous_5m':int(all(continuous)),'sigma_c':sigma,'z':r/sigma if sigma>0 else np.nan,'end_price':end,'release_return':end/p0-1,'entry_price':entry,'entry_utc':entry_t.isoformat(),'exit_price':exit,'gross_return':gross,'net_return':gross-0.0024,'mfe':mfe,'mae':mae,'keep':int(s*(end-p0)>0),'new_extreme_touch':int(s*(best-extreme)>0),'fade50_touch':int(s*(worst-p0)<=eamp*.5),'fade100_touch':int(s*(worst-p0)<=0),'fade50_end':int(s*(end-p0)<=eamp*.5),'fade100_end':int(s*(end-p0)<=0),'reverse5_touch':int(revm is not None),'reverse5_end':int(s*(end-p0)<0),'first_reverse5_min':revm,'gross_win':int(gross>0),'net_win':int(gross>0.0024),'baseline_exit_price':stop_exit,'baseline_exit_utc':stop_time.isoformat(),'baseline_exit_mfe':max(0.,float(stop_signed.max())),'baseline_exit_mae':min(0.,float(stop_signed.min())),'baseline_exit_min':stop_m,'baseline_exit_gross':s*(stop_exit/entry-1),'baseline_exit_net':s*(stop_exit/entry-1)-0.0024}
 return out

def main():
 es=pd.read_csv(ROOT/'data/events_cpi.csv');growth=pd.read_csv(ROOT/'data/growth.csv');es=es.merge(growth,on='date',how='left');out=[]
 for _,e in es.iterrows():
  p=ROOT/'data'/f'btc_{e["date"]}.csv.gz'
  if not p.exists():continue
  df=pd.read_csv(p);df['ts']=pd.to_datetime(df.ts,utc=True);df=df.set_index('ts');t0=pd.Timestamp(e.t0_utc)
  for c in [5,10,15]:
   for h in HORIZONS:
    row={**e.to_dict(),'confirm_min':c,'horizon_min':h,**calc(df,t0,c,h)};out.append(row)
 results=pd.DataFrame(out);results.to_csv(ROOT/'results/event_paths.csv',index=False,float_format='%.12g')
 main=results.loc[results.confirm_min==15];wide=es.copy()
 for h in HORIZONS:
  x=main.loc[main.horizon_min==h].drop(columns=list(es.columns)+['confirm_min','horizon_min'])
  x.insert(0,'date',main.loc[main.horizon_min==h,'date'].values)
  x=x.rename(columns={c:f'{c}_{h}m' for c in x.columns if c!='date'})
  wide=wide.merge(x,on='date',how='left')
 wide.to_csv(ROOT/'results/table_G_events.csv',index=False,float_format='%.12g')
 print('paths',results.shape,results.status.value_counts().to_dict());print('unavailable',results.loc[results.status!='ok',['date','confirm_min','horizon_min','status']].to_dict('records'))
if __name__=='__main__':main()
