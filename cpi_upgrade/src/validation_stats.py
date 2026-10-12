from common import *
from groups import make_groups
from trading import trade_stats

def hypotheses(e):
    g=make_groups(e);tests=[]
    comparisons=[('H1','H1_mild','H1_big'),('H2','H2_core_mild_cold_up','H2_core_big_cold_up'),('H3','H3_dual_extreme_hot_down','H3_dual_other_hot_down'),('H4','H4_hy_inline_up','H4_hy_cold_up'),('H5_headline','H5_hy_contrarian','H5_hy_aligned'),('H5_core','H5_cm_contrarian','H5_cm_aligned')]
    for hyp,a,b in comparisons:
        aa=e.loc[g[a]['mask']];bb=e.loc[g[b]['mask']]
        for h in [60,240]:
            tests.append({'hypothesis':hyp,'group_a':a,'group_b':b,'outcome':'net_return','horizon_min':h,**mean_test(aa[f'net_return_{h}m'],bb[f'net_return_{h}m'],hyp+str(h))})
        tests.append({'hypothesis':hyp,'group_a':a,'group_b':b,'outcome':'reverse5_touch','horizon_min':240,**rate_test(aa.reverse5_touch_240m,bb.reverse5_touch_240m)})
    t=pd.DataFrame(tests);t['q_primary']=bh(t.p);save(t,'hypothesis_tests_primary.csv')
    # Binomial reference is the fixed probability 0.5, never a synthetic event sample.
    from scipy.stats import binomtest
    actual=[]
    for k in FIELDS:
        nz=e[k+'_sign'].notna()&e[k+'_sign'].ne(0);a=np.sign(e.btc_return_15m[nz]).eq(-e.loc[nz,k+'_sign'])
        actual.append({'indicator':k,'n':len(a),'aligned_count':int(a.sum()),'p_binomial_vs05':float(binomtest(int(a.sum()),len(a),.5).pvalue),**rate(a,'alignment')})
    al=pd.DataFrame(actual);al['q_four_indicators']=bh(al.p_binomial_vs05);save(al,'indicator_direction_comparison.csv')
    return t

def robustness(e,tr):
    groups=make_groups(e);rows=[];fees=[]
    chosen=['strong_all','A_strict_monthly','B_strict_core','H1_mild','H1_big','H2_core_mild_cold_up','H2_core_big_cold_up','H4_hy_inline_up','mom_dual_extreme_hot','mom_dual_extreme_cold']
    partitions={'all':pd.Series(True,index=e.index),'2019_2023':e.year.le(2023),'2024_2026':e.year.ge(2024),'exclude2022':e.year.ne(2022),'exclude_known0830':e.other_0830_known_n.eq(0),'exclude_fomc24':e.fomc_release_within_24h.eq(0),'exclude_known0830_or_fomc24':e.other_0830_known_n.eq(0)&e.fomc_release_within_24h.eq(0)}
    for year in range(2019,2027):partitions['leaveout_'+str(year)]=e.year.ne(year)
    for stage in ['hiking','pause','cutting']:partitions['policy_'+stage]=e.policy_stage.eq(stage)
    for field in ['pandemic_crisis','high_inflation','rapid_hiking']:
        partitions['regime_'+field]=e[field].eq(True)|e[field].eq(1)
    for field in ['growth_strict','growth_snapshot']:
        for v in ['stable','deteriorating','unclassified']:partitions[field+'_'+v]=e[field].eq(v)
    variants=[('A',15,60,'absolute_event'),('A',15,240,'absolute_event'),('B',15,60,'relative_hold'),('B',15,120,'relative_hold'),('C',30,60,'relative_hold'),('C',60,240,'relative_hold')]
    primary=tr[tr.execution_lag_min.eq(1)&tr.strong_first03.eq(1)]
    for k in chosen:
        for part,mask in partitions.items():
            ids=set(e.loc[groups[k]['mask']&mask,'date']);eligible=int((groups[k]['mask']&mask&e.strong_first_03.eq(1)).sum())
            for fam,c,h,kind in variants:
                t=primary[primary.date.isin(ids)&primary.family.eq(fam)&primary.confirm_min.eq(c)&primary.horizon_min.eq(h)&primary.exit_kind.eq(kind)]
                rows.append({'group_key':k,'partition':part,'family':fam,'confirm_min':c,'horizon_min':h,'exit_kind':kind,'eligible_n':eligible,'dates':';'.join(t.date),**trade_stats(t,k+part+fam)})
                if part=='all' and len(t):
                    by=t.groupby('year').gross_return.agg(['sum','size']);yrs=by.index.to_numpy();r=rng(k+fam+str(c)+str(h)+'year')
                    sampled=r.choice(np.arange(len(yrs)),(BOOT,len(yrs)))
                    sums=by['sum'].to_numpy()[sampled].sum(axis=1);counts=by['size'].to_numpy()[sampled].sum(axis=1)
                    bs=sums/counts-.0024;lo,hi=np.quantile(bs,[.025,.975])
                    fees.append({'group_key':k,'family':fam,'confirm_min':c,'horizon_min':h,'observed_year_blocks':len(yrs),'year_block_mean_ci_low':lo,'year_block_mean_ci_high':hi,'trades_n':len(t),'historical_fee_net_mean':t.historical_fee_scenario_net.mean(),'historical_fee_net_wins':int(t.historical_fee_scenario_net.gt(0).sum()),'24bp_net_mean':t.net_return.mean()})
    save(pd.DataFrame(rows),'robustness.csv');save(pd.DataFrame(fees),'year_block_and_historical_fees.csv')
    outliers=[]
    for k in chosen:
        ids=set(e.loc[groups[k]['mask'],'date'])
        for fam,c,h,kind in variants:
            t=primary[primary.date.isin(ids)&primary.family.eq(fam)&primary.confirm_min.eq(c)&primary.horizon_min.eq(h)&primary.exit_kind.eq(kind)]
            vals=t.net_return.to_numpy();n=len(vals)
            if n<2:continue
            lo,hi=np.quantile(vals,[.05,.95]);clipped=np.clip(vals,lo,hi);leave=(vals.sum()-vals)/(n-1)
            worst=int(np.argmax(np.abs(vals)));best=int(np.argmax(vals))
            outliers.append({'group_key':k,'family':fam,'confirm_min':c,'horizon_min':h,'exit_kind':kind,'n':n,'mean_net':vals.mean(),'median_net':np.median(vals),'winsor05_95_mean':clipped.mean(),'leave_one_event_mean_min':leave.min(),'leave_one_event_mean_max':leave.max(),'largest_abs_event':t.iloc[worst].date,'excluding_largest_abs_mean':leave[worst],'best_profit_event':t.iloc[best].date,'excluding_best_profit_mean':leave[best],'status':'exploratory robustness; never used to select live trades'})
    save(pd.DataFrame(outliers),'outlier_sensitivity.csv')
    # Growth has full contemporaneous PIT employment/consumption but only partial classification.
    gg=[]
    for model in ['growth_strict','growth_snapshot']:
        for k in ['core_mom','headline_yoy']:
            for state in ['stable','deteriorating','unclassified']:
                sub=e[(e[k+'_sign']<0)&e[model].eq(state)]
                for h in [15,30,60,120,240]:
                    x=sub[f'btc_return_{h}m'].dropna();row={'growth_definition':model,'CPI_dimension':k,'growth_state':state,'horizon_min':h,'events_n':len(sub),'dates':';'.join(sub.date),**rate(x>0,'up'),**desc(x,'release_return')}
                    if h>15:
                        for flag in ['keep','fade50_touch','fade100_touch','reverse5_touch']:row.update(rate(sub[f'{flag}_{h}m'],flag))
                        row.update(desc(sub[f'net_return_{h}m'],'momentum_net'))
                    gg.append(row)
    save(pd.DataFrame(gg),'growth_environment_results.csv')
    print('robustness rows',len(rows),flush=True)

if __name__=='__main__':
    e=pd.read_csv(OUT/'events_four.csv');hypotheses(e);robustness(e,pd.read_csv(OUT/'trades_all.csv'))
