"""Replicable descriptive audit of Headline/Core CPI signals against BTC first-wave and entry P&L.
Usage: python /mnt/data/cpi_core_recheck_20261012.py
Source: /mnt/data/cpi_events(1).csv; does not fetch new data or validate the original raw source.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import fisher_exact, permutation_test
from statsmodels.stats.proportion import proportion_confint

base=Path('/mnt/data')
df=pd.read_csv(base/'cpi_events(1).csv')
for k in ['headline_yoy','headline_mom','core_yoy','core_mom']:
    df[k+'_sign']=-np.sign(df[k+'_surprise_pp']) # positive is expected bullish when cold
    df[k+'_aligned']=df[k+'_sign'].eq(np.sign(df.first_return_60m)) & df[k+'_sign'].ne(0)
df['strong_first']=df.first_return_60m.abs().ge(.003)
records=[]
def record(label,g,signcol=None,condition=''):
    o={'组别':label,'说明':condition,'事件数':len(g),'前15分钟强首波次数':int(g.strong_first.sum()), '日期':';'.join(g.date.astype(str))}
    if signcol:
        b=g[g[signcol].notna() & g[signcol].ne(0)]
        o['有明确数据方向事件数']=len(b)
        o['15分钟同方向次数']=int(b[signcol.replace('_sign','_aligned')].sum())
    else:
        o['有明确数据方向事件数']=np.nan;o['15分钟同方向次数']=np.nan
    if len(g):
        for H in [60,240]:
            n=g[f'net_return_{H}m'].notna().sum()
            o[f'{H}分钟净收益样本数']=int(n)
            o[f'{H}分钟净盈利次数']=int((g[f'net_return_{H}m']>0).sum())
            o[f'{H}分钟净均值%']=round(g[f'net_return_{H}m'].mean()*100,4)
        o['4小时5分钟确认反转次数']=int(g.reverse5_touch_240m.eq(1).sum())
        o['4小时回吐100%次数']=int(g.fade100_touch_240m.eq(1).sum())
    records.append(o)

for name in ['headline_yoy','headline_mom','core_yoy','core_mom']:
    hit=df[df[name+'_sign'].notna()&df[name+'_sign'].ne(0)]
    record(name+'意外非0（全事件）',hit,name+'_sign')
    for cls,mask in [('温和0.1pp',df[name+'_surprise_pp'].abs().round(6).eq(.1)),('显著至少0.2pp',df[name+'_surprise_pp'].abs().ge(.199999))]:
        g=df[mask & df.strong_first & df[name+'_aligned']]
        record(name+' '+cls+' 强首波顺数据交易',g,name+'_sign')

valid_core=df.core_mom_surprise_pp.notna()
head=df.headline_yoy_sign
core=df.core_mom_sign
record('总体同比符合预期，核心环比意外非0',df[head.eq(0)&core.ne(0)&valid_core], 'core_mom_sign')
record('总体同比意外非0，核心环比符合预期',df[head.ne(0)&core.eq(0)&valid_core], 'headline_yoy_sign')
record('总体同比与核心环比方向冲突',df[head.ne(0)&core.eq(-head)&valid_core], 'core_mom_sign')
record('总体同比与核心环比方向一致',df[head.ne(0)&core.eq(head)&valid_core], 'core_mom_sign')
head_mild_strong=df[head.ne(0)&df.headline_yoy_surprise_pp.abs().round(6).eq(.1)&df.strong_first&df.headline_yoy_aligned]
record('总体同比0.1pp且强首波顺数据，核心环比同向',head_mild_strong[head_mild_strong.core_mom_sign.eq(head_mild_strong.headline_yoy_sign)],'headline_yoy_sign')
record('总体同比0.1pp且强首波顺数据，核心环比中性',head_mild_strong[head_mild_strong.core_mom_sign.eq(0)],'headline_yoy_sign')
record('总体同比0.1pp且强首波顺数据，核心环比反向',head_mild_strong[head_mild_strong.core_mom_sign.eq(-head_mild_strong.headline_yoy_sign)],'headline_yoy_sign')
record('核心环比低0.1pp，BTC15分钟涨幅至少0.3%',df[df.core_mom_surprise_pp.round(6).eq(-.1) & df.first_return_60m.ge(.003)],'core_mom_sign')
record('核心环比高0.1pp，BTC15分钟跌幅至少0.3%',df[df.core_mom_surprise_pp.round(6).eq(.1) & df.first_return_60m.le(-.003)],'core_mom_sign')

output=pd.DataFrame(records)
output.to_csv(base/'CPI_核心与总体_新增对照统计_20261012.csv', index=False,encoding='utf-8-sig')

for f in ['core_mom','headline_yoy']:
    mask=df.strong_first & df[f+'_aligned']
    a=df[mask&df[f+'_surprise_pp'].abs().round(6).eq(.1)].net_return_60m.dropna().values
    b=df[mask&df[f+'_surprise_pp'].abs().ge(.199999)].net_return_60m.dropna().values
    stat=permutation_test((b,a), lambda B,A:np.mean(B)-np.mean(A), permutation_type='independent',n_resamples=20000,random_state=20261012).pvalue
    print(f,'mild',len(a),'big',len(b),'net60 mean difference pp',round((b.mean()-a.mean())*100,4),'permutation exploratory p',stat)
print('Saved:',base/'CPI_核心与总体_新增对照统计_20261012.csv')
