"""Reconcile all supplied summary rows to independently recomputed event results."""
from common import *

def main():
    inputs=ROOT/'inputs' if (ROOT/'inputs').exists() else ROOT.parent/'cpi_upgrade_inputs'
    e=pd.read_csv(OUT/'events_four.csv');rows=[]
    follow=pd.read_csv(inputs/'cpi_followup_event_audit.csv').set_index('date');now=e.set_index('date')
    pairs={'r15_pct':'btc_return_15m','keep_1h':'keep_60m','keep_4h':'keep_240m','r_15_to_1h_net24bp_pct':'net_return_60m','r_15_to_4h_net24bp_pct':'net_return_240m','fade50_touch_4h':'fade50_touch_240m','fade100_touch_4h':'fade100_touch_240m','reverse5_touch_4h':'reverse5_touch_240m'}
    for old,new in pairs.items():
        factor=100 if 'pct' in old else 1
        diff=(follow[old]-now.loc[follow.index,new]*factor).abs().max()
        rows.append({'file':'cpi_followup_event_audit.csv','row_or_field':old,'maximum_error':diff,'tolerance':.000001,'match':diff<.000001})
    old=pd.read_csv(inputs/'CPI_核心与总体_新增对照统计_20261012.csv')
    for _,r in old.iterrows():
        dates=str(r['日期']).split(';') if pd.notna(r['日期']) else []
        z=e[e.date.isin(dates)];errs=[abs(len(z)-r['事件数']),abs(int(z.strong_first_03.sum())-r['前15分钟强首波次数'])]
        for h in [60,240]:
            errs.extend([abs(z[f'net_return_{h}m'].notna().sum()-r[f'{h}分钟净收益样本数']),abs(z[f'net_return_{h}m'].gt(0).sum()-r[f'{h}分钟净盈利次数']),abs(z[f'net_return_{h}m'].mean()*100-r[f'{h}分钟净均值%'])])
        errs.extend([abs(z.reverse5_touch_240m.sum()-r['4小时5分钟确认反转次数']),abs(z.fade100_touch_240m.sum()-r['4小时回吐100%次数'])])
        err=max(errs);rows.append({'file':'CPI_核心与总体_新增对照统计_20261012.csv','row_or_field':r['组别'],'maximum_error':err,'tolerance':.000051,'match':err<.000051})
    hy=e.headline_yoy_surprise_pp;r=e.btc_return_15m;big=hy.abs().ge(.2-1e-12);hot=hy>0;cold=hy<0;strongup=r>=.003-1e-12;strongdown=r<=-.003+1e-12
    masks={
      '小幅偏热CPI + 首波下跌':hot&~big&(r<0),'明显偏热CPI + 首波下跌':hot&big&(r<0),
      '小幅偏冷CPI + 首波上涨':cold&~big&(r>0),'明显偏冷CPI + 首波上涨':cold&big&(r>0),
      '小幅偏热CPI + 首波下跌≥0.3%':hot&~big&strongdown,'小幅偏冷CPI + 首波上涨≥0.3%':cold&~big&strongup,
      '同比符合预期 + 首波上涨≥0.3%':hy.eq(0)&strongup,'同比偏冷 + 首波上涨≥0.3%':cold&strongup,
      '同比偏热 + 首波上涨≥0.3%':hot&strongup,'同比偏热 + 首波下跌≥0.3%':hot&strongdown,
      'Headline/Core同比都偏热':hot&(e.core_yoy_surprise_pp>0),'Headline/Core同比都偏冷':cold&(e.core_yoy_surprise_pp<0),
      '首波绝对幅度≥0.3%':r.abs()>=.003-1e-12,
      '温和±0.1pp + 顺方向首波≥0.3%':~big&(hot&strongdown|cold&strongup),
      '显著≥0.2pp + 顺方向首波≥0.3%':big&(hot&strongdown|cold&strongup),
    }
    old=pd.read_csv(inputs/'CPI_直接规律逐组统计_20261012.csv')
    for _,r in old.iterrows():
        period=r['年份段'];pm=e.year<=2023 if period=='2019—2023' else e.year>=2024 if period=='2024—2026' else pd.Series(True,index=e.index)
        z=e[masks[r['条件']]&pm]
        derived={'n':len(z),'前15m均值%':z.btc_return_15m.mean()*100,'公布价到1h均值%':z.btc_return_60m.mean()*100,'公布价到4h均值%':z.btc_return_240m.mean()*100,'公布价到4h中位数%':z.btc_return_240m.median()*100,'4h结束保持首波方向次':z.keep_240m.sum(),'4h期间完整回吐至公布价次':z.fade100_touch_240m.sum(),'4h期间出现5m收盘穿越公布价次':z.reverse5_touch_240m.sum(),'16m开仓到4h净盈利次':z.net_return_240m.gt(0).sum(),'16m开仓到4h净均值%(24bp成本)':z.net_return_240m.mean()*100}
        err=max(abs(derived[k]-r[k]) for k in derived)
        rows.append({'file':'CPI_直接规律逐组统计_20261012.csv','row_or_field':r['条件']+' / '+period,'maximum_error':err,'tolerance':.000051,'match':err<.000051})
    audit=pd.DataFrame(rows);save(audit,'provided_results_reconciliation.csv')
    if not audit.match.all():print(audit[~audit.match].to_string(index=False));raise ValueError('Supplied summary disagreement')
    manifest=[]
    for p in sorted(inputs.iterdir()):
        if p.suffix not in ['.csv','.pdf','.py','.md']:continue
        manifest.append({'source_type':'user supplied current Library file','file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'materialized_date':'2026-10-12','historical_availability':'original attachment; research commentary not independent market source'})
    save(pd.DataFrame(manifest),'provided_input_manifest.csv')
    print('Provided results reconciled',len(audit),'checks',flush=True)

if __name__=='__main__':main()
