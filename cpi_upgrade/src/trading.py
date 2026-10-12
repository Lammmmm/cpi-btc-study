from common import *
from groups import make_groups

def get_trade(d,t0,signal_min,entry_min,exit_min,direction):
    if exit_min<=entry_min:return None
    idx=pd.date_range(t0+pd.Timedelta(minutes=entry_min),t0+pd.Timedelta(minutes=exit_min),freq='min')
    if len(idx.difference(d.index)):return None
    entry=float(d.loc[idx[0],'open']);exit=float(d.loc[idx[-1],'open']);p=d.loc[idx[:-1]]
    prices=np.r_[p.high.to_numpy(),p.low.to_numpy(),exit];v=direction*(prices/entry-1)
    gross=float(direction*(exit/entry-1))
    return {'signal_min':signal_min,'signal_utc':(t0+pd.Timedelta(minutes=signal_min)).isoformat(),'entry_min':entry_min,'entry_utc':idx[0].isoformat(),'entry_price':entry,'exit_min':exit_min,'exit_utc':idx[-1].isoformat(),'exit_price':exit,'direction':direction,'gross_return':gross,'cost_bps':24,'net_return':gross-.0024,'net_return_cost8':gross-.0008,'net_return_cost12':gross-.0012,'net_return_cost40':gross-.004,'fees_and_slippage_usdt_per_btc':entry*.0024,'mfe':max(0.,float(v.max())),'mae':min(0.,float(v.min())),'stop_loss':'none; fixed horizon','take_profit':'none; fixed horizon'}

def main():
    e=pd.read_csv(OUT/'events_four.csv');pp=pd.read_csv(OUT/'paths.csv');rows=[];audit=[]
    for _,ev in e.iterrows():
        d=bars(ev.date);t0=pd.Timestamp(ev.t0_utc);p0=ev.p0
        context={k:ev[k] for k in ['date','year','joint_exclusive','mom_pair','mom_magnitude_pair','yoy_pair','hy_cm_pair','policy_stage','growth_strict','growth_snapshot','other_0830_known_n','fomc_release_within_24h']+[x+'_surprise_pp' for x in FIELDS]}
        for c in [5,10,15]:
            r=float(ev[f'btc_return_{c}m']);s=int(np.sign(r))
            if not s:continue
            z=pp.loc[(pp.date==ev.date)&pp.confirm_min.eq(c)&pp.horizon_min.eq(30),'z'].iloc[0]
            for lag in [0,1,2]:
                for h in [30,60,120,240]:
                    tr=get_trade(d,t0,c,c+lag,h,s)
                    if tr:
                        aligned=(ev.headline_mom_sign==ev.core_mom_sign==-s)
                        rows.append({**context,**tr,'family':'A','condition':'first-wave momentum benchmark; monthly confirmation indicated separately','confirm_min':c,'execution_lag_min':lag,'horizon_min':h,'holding_min':h-(c+lag),'exit_kind':'absolute_event','first_return':r,'first_z':z,'strong_first03':int(abs(r)>=.003-1e-12),'monthly_dual_aligned':int(aligned),'core_aligned':int(ev.core_mom_sign==-s),'eligible_strong03':int(abs(r)>=.003-1e-12),'re_reversal5':np.nan})
        c=15;r=ev.btc_return_15m;s=int(np.sign(r));strong=int(abs(r)>=.003-1e-12)
        rev=ev.first_reverse5_min_240m
        audit.append({'date':ev.date,'family':'B','eligible_initial_nonzero':int(s!=0),'eligible_strong03':strong,'eligible_strong03_core_aligned':int(strong and ev.core_mom_sign==-s),'first_trigger_min':rev,'triggered_by240':int(pd.notna(rev)),'no_trigger_by240':int(pd.isna(rev)),'trigger_observation_status':'complete 0-240m','fixed240_executable':int(pd.notna(rev) and rev+1<240)})
        if s and pd.notna(rev):
            rev=int(rev)
            for lag in [0,1,2]:
                for kind,h in [('relative_hold',15),('relative_hold',30),('relative_hold',60),('relative_hold',120),('absolute_event',240)]:
                    entry_m=rev+lag;exit_m=entry_m+h if kind=='relative_hold' else h
                    tr=get_trade(d,t0,rev,entry_m,exit_m,-s)
                    if tr:
                        marks=range(((entry_m//5)+1)*5,exit_m+1,5)
                        again=int(any(s*(float(d.loc[t0+pd.Timedelta(minutes=m-1),'close'])-p0)>0 for m in marks))
                        rows.append({**context,**tr,'family':'B','condition':'first completed 5m reversal of first-wave baseline; core agreement indicated separately','confirm_min':15,'execution_lag_min':lag,'horizon_min':h,'holding_min':exit_m-entry_m,'exit_kind':kind,'first_return':r,'first_z':ev.z_240m,'strong_first03':strong,'monthly_dual_aligned':int(ev.headline_mom_sign==ev.core_mom_sign==-s),'core_aligned':int(ev.core_mom_sign==-s),'eligible_strong03':strong,'re_reversal5':again})
        for c in [30,60]:
            still=int(s and s*ev[f'btc_return_{c}m']>0);no_pre_reverse=int(pd.isna(rev) or rev>c)
            trigger=int(still and no_pre_reverse)
            audit.append({'date':ev.date,'family':'C','confirm_min':c,'eligible_initial_nonzero':int(s!=0),'eligible_strong03':strong,'eligible_strong03_core_aligned':int(strong and ev.core_mom_sign==-s),'triggered_by240':trigger,'no_trigger_by240':1-trigger,'first_trigger_min':c if trigger else np.nan,'trigger_observation_status':'complete; no prior 5m reversal and baseline retained','fixed240_executable':np.nan})
            if trigger:
                for lag in [0,1,2]:
                    for h in [60,120,240]:
                        entry=c+lag;exit=entry+h;tr=get_trade(d,t0,c,entry,exit,s)
                        if tr:rows.append({**context,**tr,'family':'C','condition':'15m direction retained at delayed confirmation and no prior 5m reversal','confirm_min':c,'execution_lag_min':lag,'horizon_min':h,'holding_min':h,'exit_kind':'relative_hold','first_return':r,'first_z':ev.z_240m,'strong_first03':strong,'monthly_dual_aligned':int(ev.headline_mom_sign==ev.core_mom_sign==-s),'core_aligned':int(ev.core_mom_sign==-s),'eligible_strong03':strong,'re_reversal5':np.nan})
    tr=pd.DataFrame(rows);tr['trade_id']=[f'T{i:05d}' for i in range(1,len(tr)+1)]
    promo=(pd.to_datetime(tr.entry_utc,utc=True)>=pd.Timestamp('2022-07-08T14:00Z'))&(pd.to_datetime(tr.entry_utc,utc=True)<pd.Timestamp('2023-03-22T00:00Z'))
    tr['historical_fee_scenario_cost_bps']=np.where(promo,4,24);tr['historical_fee_scenario_net']=tr.gross_return-tr.historical_fee_scenario_cost_bps/10000
    save(tr,'trades_all.csv');save(pd.DataFrame(audit),'strategy_trigger_audit.csv')
    # Canonical executable results embedded once per event, with missing meaning untriggered.
    for fam,c,h,kind,name in [('A',15,60,'absolute_event','A_15_to60'),('A',15,240,'absolute_event','A_15_to240'),('B',15,60,'relative_hold','B_hold60'),('B',15,240,'absolute_event','B_to240'),('C',30,60,'relative_hold','C30_hold60'),('C',60,240,'relative_hold','C60_hold240')]:
        x=tr[tr.family.eq(fam)&tr.confirm_min.eq(c)&tr.horizon_min.eq(h)&tr.exit_kind.eq(kind)&tr.execution_lag_min.eq(1)]
        cc=['date','signal_min','entry_utc','entry_price','exit_utc','exit_price','gross_return','net_return','mfe','mae','re_reversal5']
        e=e.merge(x[cc].rename(columns={col:name+'_'+col for col in cc if col!='date'}),on='date',how='left',validate='one_to_one')
    save(e,'events_four.csv');print('trades',len(tr),'B strong triggers',len(tr[tr.family.eq('B')&tr.strong_first03.eq(1)&tr.execution_lag_min.eq(1)&tr.horizon_min.eq(60)&tr.exit_kind.eq('relative_hold')]),flush=True)

def equity_drawdown(t,frames,cost_bps):
    capital=1.;peak=1.;maxdd=0.;exitpeak=1.;exitdd=0.
    for _,r in t.sort_values('date').iterrows():
        d=frames[r.date];idx=(d.index>=pd.Timestamp(r.entry_utc))&(d.index<pd.Timestamp(r.exit_utc))
        marks=np.r_[0.,r.direction*(d.loc[idx,'close'].to_numpy()/r.entry_price-1)]-cost_bps/20000
        levels=np.r_[capital*(1+marks),capital*(1+r.gross_return-cost_bps/10000)]
        peaks=np.maximum.accumulate(np.r_[peak,levels])[1:];maxdd=min(maxdd,float(np.min(levels/peaks-1)))
        peak=max(peak,float(levels.max()));capital=levels[-1];exitpeak=max(exitpeak,capital);exitdd=min(exitdd,capital/exitpeak-1)
    return maxdd,exitdd,capital-1

def trade_stats(t,key,frames=None,cost=24):
    a=t.gross_return.to_numpy()-cost/10000;out={'trades_n':len(t)}
    out.update(rate(a>0,'net_win'));out.update(desc(a,'net_return'))
    out.update(desc(t.gross_return,'gross_return'))
    pos=a[a>0];neg=a[a<0]
    out.update(payoff_ratio=float(pos.mean()/(-neg.mean())) if len(pos) and len(neg) else np.nan,profit_factor=float(pos.sum()/(-neg.sum())) if len(neg) else np.nan,mfe_mean=t.mfe.mean(),mae_mean=t.mae.mean(),mean_zero_p=float(ttest_1samp(a,0).pvalue) if len(a)>=2 and np.std(a)>0 else np.nan)
    out.update(rate(t.re_reversal5,'re_reversal5'))
    if frames is not None:
        out['minute_close_max_drawdown'],out['exit_only_max_drawdown'],out['compound_return']=equity_drawdown(t,frames,cost)
    return out

def summarize():
    e=pd.read_csv(OUT/'events_four.csv');tr=pd.read_csv(OUT/'trades_all.csv');groups=make_groups(e)
    frames={d:bars(d) for d in e.date};rows=[]
    focus=groups.copy()
    focus['all']=groups['all']
    variants=[('A',15,h,'absolute_event') for h in [30,60,120,240]]+[('B',15,h,'relative_hold') for h in [15,30,60,120]]+[('B',15,240,'absolute_event')]+[('C',c,h,'relative_hold') for c in [30,60] for h in [60,120,240]]
    base=tr[tr.execution_lag_min.eq(1)&tr.strong_first03.eq(1)]
    for key,obj in focus.items():
        dates=set(e.loc[obj['mask'],'date']);eligible=len(dates&set(e.loc[e.strong_first_03.eq(1),'date']))
        for fam,c,h,kind in variants:
            t=base[base.date.isin(dates)&base.family.eq(fam)&base.confirm_min.eq(c)&base.horizon_min.eq(h)&base.exit_kind.eq(kind)]
            row={'group_key':key,'label':obj['label'],'family':fam,'confirm_min':c,'horizon_min':h,'exit_kind':kind,'cost_bps':24,'execution_lag_min':1,'eligible_strong15_n':eligible,'untriggered_or_not_executable_n':eligible-len(t),'low_confidence_n_lt10':len(t)<10,'dates':';'.join(t.sort_values('date').date)}
            row.update(trade_stats(t,key,frames,24));rows.append(row)
    s=pd.DataFrame(rows);s['mean_zero_q_exploratory']=bh(s.mean_zero_p);save(s,'strategy_groups.csv')
    sens=[]
    selected=['strong_all','A_strict_monthly','B_strict_core','H1_mild','H1_big','H2_core_mild_cold_up','H2_core_big_cold_up','H4_hy_inline_up','mom_dual_extreme_hot','mom_dual_extreme_cold']
    for key in selected:
        dates=set(e.loc[groups[key]['mask'],'date'])
        for fam,c,h,kind in [('A',15,60,'absolute_event'),('A',15,240,'absolute_event'),('B',15,60,'relative_hold'),('B',15,120,'relative_hold'),('C',30,60,'relative_hold'),('C',60,240,'relative_hold')]:
            for lag in [0,1,2]:
                t=tr[tr.date.isin(dates)&tr.family.eq(fam)&tr.confirm_min.eq(c)&tr.horizon_min.eq(h)&tr.exit_kind.eq(kind)&tr.execution_lag_min.eq(lag)&tr.strong_first03.eq(1)]
                for cost in [8,12,24,40]:sens.append({'group_key':key,'family':fam,'confirm_min':c,'horizon_min':h,'exit_kind':kind,'cost_bps':cost,'execution_lag_min':lag,**trade_stats(t,key+str(lag)+str(cost),None,cost)})
    save(pd.DataFrame(sens),'cost_latency_sensitivity.csv')
    threshold=[]
    for fam,c,h,kind in [('A',c,h,'absolute_event') for c in [5,10,15] for h in [30,60,240]]+[('B',15,60,'relative_hold'),('C',30,60,'relative_hold'),('C',60,240,'relative_hold')]:
        for label,filt in [('abs02',tr.first_return.abs().ge(.002-1e-12)),('abs03',tr.first_return.abs().ge(.003-1e-12)),('abs05',tr.first_return.abs().ge(.005-1e-12)),('z1',tr.first_z.abs().ge(1)),('z2',tr.first_z.abs().ge(2))]:
            t=tr[filt&tr.family.eq(fam)&tr.confirm_min.eq(c)&tr.horizon_min.eq(h)&tr.exit_kind.eq(kind)&tr.execution_lag_min.eq(1)]
            threshold.append({'family':fam,'confirm_min':c,'horizon_min':h,'exit_kind':kind,'threshold':label,**trade_stats(t,label+str(c),None)})
    save(pd.DataFrame(threshold),'firstwave_threshold_sensitivity.csv')
    confirmations=[]
    for c in [5,10,15]:
        for h in [30,60,120,240]:
            for split in ['all','2019_2023','2024_2026','exclude2022']:
                t=tr[tr.family.eq('A')&tr.confirm_min.eq(c)&tr.horizon_min.eq(h)&tr.execution_lag_min.eq(1)&tr.first_return.abs().ge(.003-1e-12)&tr.monthly_dual_aligned.eq(1)]
                if split=='2019_2023':t=t[t.year<=2023]
                elif split=='2024_2026':t=t[t.year>=2024]
                elif split=='exclude2022':t=t[t.year!=2022]
                confirmations.append({'family':'A_monthly_confirmed','confirm_min':c,'horizon_min':h,'split':split,'entry_min':c+1,'cost_bps':24,'threshold_abs':.003,'dates':';'.join(t.date),**trade_stats(t,'confirmed'+str(c)+str(h)+split,frames)})
    cf=pd.DataFrame(confirmations);cf['q_confirmation_exploratory']=bh(cf.mean_zero_p);save(cf,'A_monthly_confirmation.csv')
    print('strategy group rows',len(s),'sensitivity',len(sens),flush=True)

if __name__=='__main__':
    import sys
    summarize() if '--summarize' in sys.argv else main()
