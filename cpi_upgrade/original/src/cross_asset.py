"""Optional actual cross-asset verification. Never uses daily yield as intraday data.
Input schema: minute-start timestamp, rate_pct (2Y closing yield, percent), nq_close.
ZT prices alone do not satisfy rate_pct; require an independently documented DV01 calibration.
"""
from net import ROOT
from summarize import summary,compare,bh
import pandas as pd,numpy as np,argparse

def main(path):
 df=pd.read_csv(path)
 for col in ['timestamp','rate_pct','nq_close']:
  if col not in df:raise ValueError('Missing required field '+col)
 df['timestamp']=pd.to_datetime(df.timestamp,utc=True);df=df.set_index('timestamp').sort_index()
 if df.index.duplicated().any():raise ValueError('Duplicate cross-asset timestamps')
 if df.empty:raise ValueError('No observed cross-asset records: cannot test H2/H4')
 paths=pd.read_csv(ROOT/'results/event_paths.csv');base=paths[(paths.confirm_min==15)&(paths.status=='ok')];events=pd.read_csv(ROOT/'data/events_cpi.csv');rows=[];audit=[];landmarks=[];trades=[]
 for _,e in events.iterrows():
  t0=pd.Timestamp(e.t0_utc);need=pd.date_range(t0-pd.Timedelta(minutes=1),t0+pd.Timedelta(minutes=240),freq='min')
  if len(need.difference(df.index)):
   audit.append({'date':e['date'],'status':'cross_asset_window_incomplete'});continue
  z=df.loc[need]
  if z[['rate_pct','nq_close']].isna().any().any():audit.append({'date':e['date'],'status':'missing_values'});continue
  y0=float(z.iloc[0].rate_pct);q0=float(z.iloc[0].nq_close);dy=(float(z.loc[t0+pd.Timedelta(minutes=14),'rate_pct'])-y0)*100;rq=float(z.loc[t0+pd.Timedelta(minutes=14),'nq_close'])/q0-1
  rs=int(np.sign(dy)) if abs(dy)>=2 else 0;ns=int(np.sign(rq)) if abs(rq)>=.001 else 0
  state=('2Y_down' if rs==-1 else '2Y_up' if rs==1 else '2Y_ambiguous')+'_'+('NQ_up' if ns==1 else 'NQ_down' if ns==-1 else 'NQ_ambiguous')
  reversals=[]
  if rs:
   for m in range(20,241,5):
    d=(float(z.loc[t0+pd.Timedelta(minutes=m-1),'rate_pct'])-y0)*100
    if rs*d<=-2:reversals.append(m)
  first_rate_rev=min(reversals) if reversals else np.nan
  for h in [30,60,240]:
   b=base[(base.date==e['date'])&(base.horizon_min==h)]
   if b.empty:continue
   b=b.iloc[0];aligned=bool(rs and b.direction==-rs and abs(b.first_return)>=.003)
   row={**b.to_dict(),'cross_state':state,'rate15_bp':dy,'nq15_return':rq,'rate_btc_aligned':aligned,'rate_first_reverse_min':first_rate_rev,'rate_ever_reversed_by_h':int(any(m<=h for m in reversals)),'nq_end_return':float(z.loc[t0+pd.Timedelta(minutes=h-1),'nq_close'])/q0-1};rows.append(row)
   if aligned:
    f=ROOT/'data'/f'btc_{e["date"]}.csv.gz';btc=pd.read_csv(f);btc['ts']=pd.to_datetime(btc.ts,utc=True);btc=btc.set_index('ts')
    m=next((m for m in reversals if m+1<h),None);ep=float(btc.loc[t0+pd.Timedelta(minutes=m+1),'open']) if m else b.exit_price
    gross=b.direction*(ep/b.entry_price-1);trades.append({'date':e['date'],'horizon_min':h,'rate_exit_trigger_min':m,'rate_exit_net':gross-.0024,'fixed_net':b.net_return,'improvement':gross-.0024-b.net_return})
   if h==240 and aligned:
    for L in [30,60]:
     close=float(btc.loc[t0+pd.Timedelta(minutes=L-1),'close'])
     # Exclude BTC already reversed by landmark; only subsequent outcomes count.
     earlier=[m for m in range(20,L+1,5) if b.direction*(float(btc.loc[t0+pd.Timedelta(minutes=m-1),'close'])-b.p0)<0]
     if earlier:continue
     later=[m for m in range(L+5,241,5) if b.direction*(float(btc.loc[t0+pd.Timedelta(minutes=m-1),'close'])-b.p0)<0]
     rr=any(m<=L for m in reversals)
     lead=(min(later)-first_rate_rev) if rr and later else np.nan
     landmarks.append({'date':e['date'],'landmark_min':L,'rate_reversed_known_at_landmark':int(rr),'btc_future_reverse':int(bool(later)),'rate_to_btc_lead_minutes':lead,'rate_reversal_false_positive':int(rr and not later)})
  audit.append({'date':e['date'],'status':'verified_complete'})
 if not rows:raise ValueError('No complete observed joint events: H2/H4 remain unverified')
 out=ROOT/'results/cross_asset_observed';out.mkdir(exist_ok=True);pd.DataFrame(audit).to_csv(out/'audit.csv',index=False);r=pd.DataFrame(rows);r.to_csv(out/'event_paths.csv',index=False);d=[]
 for (state,h),g in r.groupby(['cross_state','horizon_min']):d.append({'state':state,'horizon_min':h,**summary(g)})
 pd.DataFrame(d).to_csv(out/'table_D.csv',index=False)
 lm=pd.DataFrame(landmarks);lm.to_csv(out/'landmark_events.csv',index=False);tests=[]
 if not lm.empty:
  for L,g in lm.groupby('landmark_min'):
   a=g[g.rate_reversed_known_at_landmark==1];b=g[g.rate_reversed_known_at_landmark==0];tests.append(compare(a,b,'btc_future_reverse',f'H4_landmark{L}',True))
  t=pd.DataFrame(tests);t['q_value']=bh(t.p_value);t.to_csv(out/'table_E.csv',index=False)
 pd.DataFrame(trades).to_csv(out/'rate_exit_trades.csv',index=False)
 print('Observed cross-asset analysis saved; inspect missing dates and product calibration metadata.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('input_csv');args=ap.parse_args();main(args.input_csv)
