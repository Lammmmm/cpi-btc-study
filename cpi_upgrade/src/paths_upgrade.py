import sys
import numpy as np
import pandas as pd
from common import *
sys.path.append(str(ORIGINAL/'src'))
from backtest import calc

def bucket(x):
    if pd.isna(x):return '缺失'
    n=int(np.rint(x*10))
    return '暴冷' if n<=-2 else '小幅偏冷' if n==-1 else '符合预期' if n==0 else '小幅偏热' if n==1 else '暴热'

def exclusive(e):
    h,c,hy,cy=[e[k+'_sign'] for k in FIELDS]
    if any(pd.isna(x) for x in [h,c]):return '00_月率缺失'
    if all(x==0 for x in [h,c,hy,cy]):return '01_四项全符合'
    if all(x<0 for x in [h,c,hy,cy]):return '02_四项全冷'
    if all(x>0 for x in [h,c,hy,cy]):return '03_四项全热'
    if h*c<0:return '04_月率冲突'
    if h==c and h!=0 and (h*hy<0 or h*cy<0):return '05_月率一致同比反向'
    if h==c==-1:return '06_月率双冷其余'
    if h==c==1:return '07_月率双热其余'
    if h==0 and c!=0:return '08_总体月率中性核心意外'
    if c==0 and h!=0:return '09_核心月率中性总体意外'
    return '10_其他混合'

def main():
    original=pd.read_csv(ORIGINAL/'results/table_G_events.csv')
    cols=[c for c in original if not any(c.endswith('_'+str(h)+'m') for h in [30,60,240,1440]) and not c.startswith('2Y_')]
    e=original[cols].copy().sort_values('date').reset_index(drop=True)
    conf=pd.read_csv(ORIGINAL/'results/simultaneous_releases.csv')
    for col in conf.columns:
        if col!='date' and col in e:e=e.drop(columns=[col])
    e=e.merge(conf,on='date',validate='one_to_one')
    for k in FIELDS:
        # Rounding input displayed tenths before subtraction avoids binary float boundaries.
        a=(e[k+'_actual']*10).round();f=(e[k+'_forecast']*10).round()
        e[k+'_surprise_pp']=(a-f)/10
        e[k+'_sign']=np.sign(e[k+'_surprise_pp'])
        e[k+'_bucket5']=e[k+'_surprise_pp'].map(bucket)
        e[k+'_extreme03']=e[k+'_surprise_pp'].abs().ge(.3-1e-12).where(e[k+'_surprise_pp'].notna())
        vals=e[k+'_surprise_pp'].to_numpy()
        std=pd.Series([np.std(p,ddof=1) if len(p)>=12 else np.nan for i in range(len(vals)) for p in [vals[:i][np.isfinite(vals[:i])][-24:]]],index=e.index)
        e[k+'_rolling_prior_sigma_pp']=std
        e[k+'_surprise_z_prior24']=e[k+'_surprise_pp']/std.where(std>0)
        e[k+'_actual_source']=e.url
        e[k+'_forecast_availability']='retrospective historical calendar; not certified 08:29 snapshot'
        e.loc[e[k+'_forecast'].isna(),k+'_forecast_availability']='missing; no substitution'
    e['joint_exclusive']=e.apply(exclusive,axis=1)
    for tag,a,b in [('mom','headline_mom','core_mom'),('yoy','headline_yoy','core_yoy'),('hy_cm','headline_yoy','core_mom')]:
        e[tag+'_pair']=e.apply(lambda x:'缺失' if pd.isna(x[a+'_sign']) or pd.isna(x[b+'_sign']) else LABELS[int(x[a+'_sign'])]+' / '+LABELS[int(x[b+'_sign'])],axis=1)
        e[tag+'_magnitude_pair']=e[a+'_bucket5']+' / '+e[b+'_bucket5']
    audit=[];paths=[];allframes={};features=[]
    for i,row in e.iterrows():
        d=bars(row.date);allframes[row.date]=d;t0=pd.Timestamp(row.t0_utc)
        required=pd.date_range(t0-pd.Timedelta(minutes=60),t0+pd.Timedelta(minutes=1440),freq='min')
        missing=required.difference(d.index)
        au={'date':row.date,'bars':len(d),'expected_bars':1501,'missing_minutes':len(missing),'duplicates':int(d.index.duplicated().sum()),'bad_ohlc':int(((d.high<d[['open','close','low']].max(axis=1))|(d.low>d[['open','close','high']].min(axis=1))).sum()),'missing_start':str(missing.min()) if len(missing) else '', 'missing_end':str(missing.max()) if len(missing) else ''}
        audit.append(au);p0=float(d.loc[t0-pd.Timedelta(minutes=1),'close']);ed={'p0':p0}
        for h in HORIZONS:
            need=pd.date_range(t0-pd.Timedelta(minutes=1),t0+pd.Timedelta(minutes=h),freq='min')
            valid=not len(need.difference(d.index));ed[f'price_path_complete_{h}m']=int(valid)
            ed[f'btc_return_{h}m']=float(d.loc[t0+pd.Timedelta(minutes=h-1),'close']/p0-1) if valid else np.nan
            ed[f'btc_close_{h}m']=float(d.loc[t0+pd.Timedelta(minutes=h-1),'close']) if valid else np.nan
        for c in [5,10,15]:
            for h in [30,60,120,240,1440]:
                r=calc(d,t0,c,h);r.update(date=row.date,confirm_min=c,horizon_min=h)
                if r['status']=='ok':
                    rm=r['first_reverse5_min']
                    r['post_reverse_follow_through']=np.nan if rm is None or rm>=h else int(-r['direction']*(r['end_price']/float(d.loc[t0+pd.Timedelta(minutes=rm-1),'close'])-1)>0)
                    r['new_extreme_end']=int(r['direction']*(r['end_price']-r['first_extreme'])>0)
                    r['up_then_down_end']=int(r['direction']==1 and r['release_return']<0)
                    r['down_then_up_end']=int(r['direction']==-1 and r['release_return']>0)
                    if c==15:
                        for key,value in r.items():
                            if key not in ['date','confirm_min','horizon_min']:ed[f'{key}_{h}m']=value
                elif c==15:ed[f'status_{h}m']=r['status']
                paths.append(r)
        ed['btc_first_direction']=int(np.sign(ed['btc_return_15m']))
        ed['strong_first_03']=int(abs(ed['btc_return_15m'])>=.003-1e-12)
        ed['strong_first_05']=int(abs(ed['btc_return_15m'])>=.005-1e-12)
        features.append(ed)
    e=pd.concat([e,pd.DataFrame(features)],axis=1)
    save(e,'events_four.csv');save(pd.DataFrame(paths),'paths.csv');save(pd.DataFrame(audit),'minute_audit.csv')
    # Independent comparison to all original short-horizon results, not copied values.
    delta=[]
    for h in [30,60,240]:
        for key in ['first_return','release_return','keep','fade100_touch','reverse5_touch','gross_return','net_return']:
            diff=float(np.max(np.abs(e[f'{key}_{h}m'].to_numpy()-original.sort_values('date')[f'{key}_{h}m'].to_numpy())))
            delta.append({'horizon_min':h,'field':key,'max_error':diff})
    save(pd.DataFrame(delta),'original_recompute_audit.csv')
    print('paths',len(paths),'events',len(e),'joint',e.joint_exclusive.value_counts().to_dict(),flush=True)
    return e,allframes

if __name__=='__main__':main()
