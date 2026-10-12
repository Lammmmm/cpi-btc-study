from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, ttest_1samp

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'original' if (ROOT / 'original').exists() else ROOT.parent / 'cpi_study'
OUT = ROOT / 'results'
DEL = ROOT / 'deliverables'
FIELDS = ['headline_mom', 'core_mom', 'headline_yoy', 'core_yoy']
HORIZONS = [5, 10, 15, 30, 60, 120, 240, 1440]
SEED = 20261012
BOOT = 10000
LABELS = {-1: '偏冷', 0: '符合', 1: '偏热'}

def rng(key):
    return np.random.default_rng(SEED + int(hashlib.sha256(str(key).encode()).hexdigest()[:8], 16))

def save(df, name):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, encoding='utf-8-sig', float_format='%.12g')
    return p

def wilson(k, n):
    if n == 0: return np.nan, np.nan
    z = 1.959963984540054; p = k/n; d = 1+z*z/n
    mid=(p+z*z/(2*n))/d; half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0.,mid-half), min(1.,mid+half)

def rate(x, key):
    a=pd.Series(x).dropna().astype(float); n=len(a); k=int(a.sum())
    lo,hi=wilson(k,n)
    return {key+'_n':n, key+'_count':k, key+'_rate':k/n if n else np.nan, key+'_ci_low':lo, key+'_ci_high':hi}

def boot_mean(x, key):
    a=np.asarray(x,dtype=float); a=a[np.isfinite(a)]
    if len(a)<2: return np.nan,np.nan
    vals=rng(key).choice(a,(BOOT,len(a)),replace=True).mean(axis=1)
    return tuple(np.quantile(vals,[.025,.975]))

def desc(x,key):
    a=np.asarray(x,dtype=float); a=a[np.isfinite(a)]; n=len(a)
    lo,hi=boot_mean(a,key)
    z={key+'_n':n, key+'_mean':float(a.mean()) if n else np.nan, key+'_median':float(np.median(a)) if n else np.nan, key+'_mean_ci_low':lo, key+'_mean_ci_high':hi}
    for label,q in [('min',0),('p10',.1),('p25',.25),('p75',.75),('p90',.9),('max',1)]:
        z[key+'_'+label]=float(np.quantile(a,q)) if n else np.nan
    return z

def bh(ps):
    ps=np.asarray(ps,dtype=float); out=np.full(len(ps),np.nan); valid=np.flatnonzero(np.isfinite(ps))
    if len(valid):
        order=valid[np.argsort(ps[valid])]; q=ps[order]*len(order)/np.arange(1,len(order)+1)
        out[order]=np.minimum(1,np.minimum.accumulate(q[::-1])[::-1])
    return out

def mean_test(a,b,key):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float);a=a[np.isfinite(a)];b=b[np.isfinite(b)]
    o={'n_a':len(a),'n_b':len(b),'effect_a_minus_b':np.nan,'ci_low':np.nan,'ci_high':np.nan,'p':np.nan,'method':'independent permutation / independent event bootstrap'}
    if not len(a) or not len(b):return o
    observed=float(a.mean()-b.mean());o['effect_a_minus_b']=observed
    if min(len(a),len(b))<2:return o
    r=rng(key);diff=r.choice(a,(BOOT,len(a))).mean(axis=1)-r.choice(b,(BOOT,len(b))).mean(axis=1)
    o['ci_low'],o['ci_high']=np.quantile(diff,[.025,.975]);combined=np.r_[a,b];n=len(a)
    perms=np.array([r.permutation(combined) for _ in range(BOOT)])
    sim=perms[:,:n].mean(axis=1)-perms[:,n:].mean(axis=1)
    o['p']=(1+int((np.abs(sim)>=abs(observed)-1e-15).sum()))/(BOOT+1)
    return o

def rate_test(a,b):
    a=pd.Series(a).dropna().astype(int);b=pd.Series(b).dropna().astype(int);na=len(a);nb=len(b)
    o={'n_a':na,'n_b':nb,'count_a':int(a.sum()),'count_b':int(b.sum()),'effect_a_minus_b':np.nan,'ci_low':np.nan,'ci_high':np.nan,'p':np.nan,'method':'Fisher two-sided / Newcombe Wilson difference'}
    if not na or not nb:return o
    pa=a.mean();pb=b.mean();la,ua=wilson(a.sum(),na);lb,ub=wilson(b.sum(),nb)
    o.update(effect_a_minus_b=pa-pb,ci_low=pa-pb-np.sqrt((pa-la)**2+(ub-pb)**2),ci_high=pa-pb+np.sqrt((ua-pa)**2+(pb-lb)**2),p=float(fisher_exact([[int(a.sum()),na-int(a.sum())],[int(b.sum()),nb-int(b.sum())]]).pvalue))
    return o

def jdump(obj,p):
    Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def bars(date):
    d=pd.read_csv(ORIGINAL/'data'/f'btc_{date}.csv.gz');d.ts=pd.to_datetime(d.ts,utc=True)
    return d.set_index('ts').sort_index()
