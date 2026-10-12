#!/usr/bin/env python3
"""CPI/BTC rule mining (exploratory, NOT validated live strategies).
Usage: python cpi_规律复算_20261012.py '/path/to/cpi_events(1).csv'
Source: user-supplied 92-event historical CSV. Does not independently audit its raw 1m candles.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.stats import permutation_test, fisher_exact
from statsmodels.stats.multitest import multipletests

src=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('cpi_events(1).csv')
out=Path(__file__).with_name('CPI_直接规律逐组统计_20261012.csv')
d=pd.read_csv(src)
assert len(d)==92, f'Expected 92 events, got {len(d)}'
d['first15_pct']=d.first_return_30m*100
d['big_surprise']=d.headline_yoy_surprise_pp.abs()>=.2-1e-8
d['strong_up']=d.first15_pct>=.3-1e-8
d['strong_down']=d.first15_pct<=-.3+1e-8
hot=d.headline_yoy_class.eq('hot')
cold=d.headline_yoy_class.eq('cold')
inln=d.headline_yoy_class.eq('inline')
up=d.first15_pct>0
down=d.first15_pct<0
big=d.big_surprise
conditions={
'小幅偏热CPI + 首波下跌':hot&(~big)&down,
'明显偏热CPI + 首波下跌':hot&big&down,
'小幅偏冷CPI + 首波上涨':cold&(~big)&up,
'明显偏冷CPI + 首波上涨':cold&big&up,
'小幅偏热CPI + 首波下跌≥0.3%':hot&(~big)&d.strong_down,
'小幅偏冷CPI + 首波上涨≥0.3%':cold&(~big)&d.strong_up,
'同比符合预期 + 首波上涨≥0.3%':inln&d.strong_up,
'同比偏冷 + 首波上涨≥0.3%':cold&d.strong_up,
'同比偏热 + 首波上涨≥0.3%':hot&d.strong_up,
'同比偏热 + 首波下跌≥0.3%':hot&d.strong_down,
'Headline/Core同比都偏热':hot&d.core_yoy_class.eq('hot'),
'Headline/Core同比都偏冷':cold&d.core_yoy_class.eq('cold'),
'首波绝对幅度≥0.3%':d.first15_pct.abs()>=.3-1e-8,
'温和±0.1pp + 顺方向首波≥0.3%':(~big)&(hot&d.strong_down|cold&d.strong_up),
'显著≥0.2pp + 顺方向首波≥0.3%':big&(hot&d.strong_down|cold&d.strong_up),
}
rows=[]
for label,mask in conditions.items():
 for subname,mask2 in [('全部',d.year>=2019),('2019—2023',d.year<=2023),('2024—2026',d.year>=2024)]:
  t=d[mask&mask2];n=len(t)
  if not n:continue
  row={'条件':label,'年份段':subname,'n':n,
       '前15m均值%':100*t.first_return_30m.mean(),
       '公布价到1h均值%':100*t.release_return_60m.mean(),
       '公布价到4h均值%':100*t.release_return_240m.mean(),
       '公布价到4h中位数%':100*t.release_return_240m.median(),
       '4h结束保持首波方向次':int(t.keep_240m.sum()),
       '4h期间完整回吐至公布价次':int(t.fade100_touch_240m.sum()),
       '4h期间出现5m收盘穿越公布价次':int(t.reverse5_touch_240m.sum()),
       '16m开仓到4h净盈利次':int((t.net_return_240m>0).sum()),
       '16m开仓到4h净均值%(24bp成本)':100*t.net_return_240m.mean()}
  rows.append(row)
output=pd.DataFrame(rows)
output.to_csv(out,index=False,encoding='utf-8-sig')
print('Saved',out,'rows',len(output))
# Design note: exploratory p-values are biased by hypothesis selection from historical data.
conds=conditions
sel=[
('温和vs显著:顺方向强首波后1h净收益','温和±0.1pp + 顺方向首波≥0.3%','显著≥0.2pp + 顺方向首波≥0.3%','net_return_60m'),
('温和vs显著:顺方向强首波后4h净收益','温和±0.1pp + 顺方向首波≥0.3%','显著≥0.2pp + 顺方向首波≥0.3%','net_return_240m'),
('温和热跌 vs 显著热跌:4h公布价回报','小幅偏热CPI + 首波下跌','明显偏热CPI + 首波下跌','release_return_240m'),
('温和热跌 vs 显著热跌:4h追空收益','小幅偏热CPI + 首波下跌','明显偏热CPI + 首波下跌','net_return_240m'),
('温和冷涨 vs 显著冷涨:4h公布价回报','小幅偏冷CPI + 首波上涨','明显偏冷CPI + 首波上涨','release_return_240m'),
('符合强涨 vs 偏冷强涨:4h追涨收益','同比符合预期 + 首波上涨≥0.3%','同比偏冷 + 首波上涨≥0.3%','net_return_240m'),
('符合强涨 vs 偏热强涨:4h追涨收益','同比符合预期 + 首波上涨≥0.3%','同比偏热 + 首波上涨≥0.3%','net_return_240m'),
('双热 vs 双冷:4h公布价回报','Headline/Core同比都偏热','Headline/Core同比都偏冷','release_return_240m'),
]
ps=[];tests=[]
for name,a,b,col in sel:
 x=d.loc[conds[a],col].to_numpy();y=d.loc[conds[b],col].to_numpy()
 r=permutation_test((x,y),lambda xx,yy:np.mean(xx)-np.mean(yy),n_resamples=40000,random_state=20261012)
 ps.append(r.pvalue);tests.append((name,len(x),len(y),100*(x.mean()-y.mean()),r.pvalue))
for (name,n1,n2,diff,p),q in zip(tests,multipletests(ps,method='fdr_bh')[1]):
 print(f'{name}: n={n1}/{n2}, 差={diff:+.3f}个百分点, 探索置换p={p:.4f}, 针对本8项BH q={q:.4f}')
