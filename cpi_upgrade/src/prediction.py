from common import *
from scipy.special import expit
from scipy.optimize import minimize

FEATURES={'headline':['headline_mom','headline_yoy'],'core':['core_mom','core_yoy'],'combined':FIELDS,'headline_mom_only':['headline_mom'],'core_mom_only':['core_mom'],'constant':[]}

def fit_predict(x,y,test,penalty=1.):
    if x.shape[1]==0:return np.full(len(test),float(np.mean(y)))
    mean=x.mean(axis=0);std=x.std(axis=0);std[std==0]=1
    xx=np.c_[np.ones(len(x)),(x-mean)/std];tt=np.c_[np.ones(len(test)),(test-mean)/std]
    def objective(b):
        z=xx@b;p=expit(z)
        return float(np.logaddexp(0,z).sum()-np.dot(y,z)+.5*penalty*np.dot(b[1:],b[1:])),xx.T@(p-y)+np.r_[0.,penalty*b[1:]]
    init=np.zeros(xx.shape[1]);result=minimize(objective,init,method='L-BFGS-B',jac=True,options={'ftol':1e-12,'gtol':1e-8,'maxiter':1000})
    if not result.success:raise RuntimeError(result.message)
    return expit(tt@result.x)

def metrics(y,p):
    p=np.clip(np.asarray(p),1e-12,1-1e-12);y=np.asarray(y)
    return {'n':len(y),'accuracy':float(np.mean((p>=.5)==y)),'correct_count':int(((p>=.5)==y).sum()),'brier_score':float(np.mean((p-y)**2)),'log_loss':float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p)))}

def paired_diff(a,b,key):
    v=np.asarray(a)-np.asarray(b);n=len(v);r=rng(key);bs=r.choice(v,(BOOT,n)).mean(axis=1);obs=float(v.mean())
    signs=r.choice([-1,1],(BOOT,n));sim=(signs*v).mean(axis=1)
    return {'effect_combined_minus_headline':obs,'ci_low':float(np.quantile(bs,.025)),'ci_high':float(np.quantile(bs,.975)),'p':float((1+(np.abs(sim)>=abs(obs)-1e-15).sum())/(BOOT+1)),'n':n,'method':'paired event bootstrap and sign-flip randomization; exploratory'}

def main():
    e=pd.read_csv(OUT/'events_four.csv').sort_values('date');valid=e[[k+'_surprise_pp' for k in FIELDS]].notna().all(axis=1)
    predictions=[];summaries=[]
    for target in ['first15_up','keep4h_strong']:
        t=e[valid].copy()
        if target=='keep4h_strong':t=t[t.strong_first_03.eq(1)]
        t['target']=(t.btc_return_15m>0).astype(int) if target=='first15_up' else t.keep_240m.astype(int)
        for split,cut,test_end in [('holdout_2024_2026',2023,2026)]+[('walk_'+str(y),y-1,y) for y in range(2022,2027)]:
            train=t[t.year<=cut];test=t[(t.year>cut)&(t.year<=test_end)]
            if not len(test):continue
            for model,fields in FEATURES.items():
                if target=='first15_up':
                    x=train[[f+'_surprise_pp' for f in fields]].to_numpy();z=test[[f+'_surprise_pp' for f in fields]].to_numpy()
                else:
                    # Common known first-wave amplitude for every CPI model; signed shocks describe agreement.
                    x=train[[f+'_surprise_pp' for f in fields]].to_numpy()*train.btc_first_direction.to_numpy()[:,None]
                    z=test[[f+'_surprise_pp' for f in fields]].to_numpy()*test.btc_first_direction.to_numpy()[:,None]
                    if model!='constant':x=np.c_[x,train.btc_return_15m.abs()];z=np.c_[z,test.btc_return_15m.abs()]
                p=fit_predict(x,train.target.to_numpy(),z)
                m=metrics(test.target,p);lo,hi=wilson(m['correct_count'],m['n'])
                summaries.append({'target':target,'split':split,'model':model,'train_n':len(train),'train_last_date':train.date.max(),'test_first_date':test.date.min(),**m,'accuracy_ci_low':lo,'accuracy_ci_high':hi,'regularization_lambda':1.,'historical_holdout_not_unseen':True})
                for (_,r),prob in zip(test.iterrows(),p):predictions.append({'date':r.date,'target_name':target,'split':split,'model':model,'actual_target':int(r.target),'probability':float(prob),'predicted_target':int(prob>=.5),'train_last_date':train.date.max()})
    p=pd.DataFrame(predictions);s=pd.DataFrame(summaries);diff=[]
    for target in p.target_name.unique():
        for split in ['holdout_2024_2026','walk_forward_2022_2026']:
            z=p[p.target_name.eq(target)&(p.split.str.startswith('walk_') if split.startswith('walk_') else p.split.eq(split))]
            if split.startswith('walk_'):
                for model in FEATURES:
                    mm=z[z.model.eq(model)];m=metrics(mm.actual_target,mm.probability);lo,hi=wilson(m['correct_count'],m['n']);s=pd.concat([s,pd.DataFrame([{'target':target,'split':split,'model':model,**m,'accuracy_ci_low':lo,'accuracy_ci_high':hi,'historical_holdout_not_unseen':True}])],ignore_index=True)
            wide=z.pivot(index='date',columns='model',values='probability');y=z.drop_duplicates('date').set_index('date').actual_target.reindex(wide.index).to_numpy()
            for metric in ['brier','log_loss']:
                losses={}
                for model in ['combined','headline']:
                    v=np.clip(wide[model].to_numpy(),1e-12,1-1e-12);losses[model]=(v-y)**2 if metric=='brier' else -y*np.log(v)-(1-y)*np.log(1-v)
                diff.append({'target':target,'split':split,'metric':metric,**paired_diff(losses['combined'],losses['headline'],target+split+metric)})
    d=pd.DataFrame(diff);d['q_prediction_exploratory']=bh(d.p)
    save(p,'prediction_events.csv');save(s,'prediction_metrics.csv');save(d,'prediction_incremental_tests.csv')
    print(s[s.split.eq('holdout_2024_2026')][['target','model','n','accuracy','brier_score','log_loss']].to_string(index=False),flush=True)

if __name__=='__main__':main()
