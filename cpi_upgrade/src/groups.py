from common import *

def make_groups(e):
    groups={}
    def add(key,label,mask,family):
        groups[key]={'label':label,'mask':pd.Series(mask,index=e.index).fillna(False).astype(bool),'family':family}
    add('all','全部正式事件',pd.Series(True,index=e.index),'base')
    for k in FIELDS:
        for cls in ['暴冷','小幅偏冷','符合预期','小幅偏热','暴热','缺失']:
            add(k+'_'+cls,k+' '+cls,e[k+'_bucket5'].eq(cls),'single')
        for s in [-1,0,1]:add(k+'_sign_'+str(s),k+' '+LABELS[s],e[k+'_sign'].eq(s),'single3')
        for s in [-1,1]:
            add(k+'_extreme03_'+str(s),k+' 绝对意外>=0.3pp '+LABELS[s],e[k+'_surprise_pp'].abs().ge(.3-1e-12)&e[k+'_sign'].eq(s),'extreme03')
            add(k+'_z2_'+str(s),k+' 历史标准化绝对z>=2 '+LABELS[s],e[k+'_surprise_z_prior24'].abs().ge(2)&e[k+'_sign'].eq(s),'standardized')
    for tag,a,b in [('mom','headline_mom','core_mom'),('yoy','headline_yoy','core_yoy'),('hy_cm','headline_yoy','core_mom')]:
        for sa in [-1,0,1]:
            for sb in [-1,0,1]:
                m=e[a+'_sign'].eq(sa)&e[b+'_sign'].eq(sb)
                add(f'{tag}_{sa}_{sb}',f'{tag} 总体{LABELS[sa]}、核心{LABELS[sb]}',m,'matrix_'+tag)
                add(f'{tag}_{sa}_{sb}_strong',f'{tag} 总体{LABELS[sa]}、核心{LABELS[sb]} 强首波',m&e.strong_first_03.eq(1),'matrix_strong_'+tag)
        add(tag+'_missing',tag+' 数据缺失',e[a+'_sign'].isna()|e[b+'_sign'].isna(),'matrix_'+tag)
        for ca in ['暴冷','小幅偏冷','符合预期','小幅偏热','暴热']:
            for cb in ['暴冷','小幅偏冷','符合预期','小幅偏热','暴热']:
                add(tag+'_mag_'+ca+'_'+cb,tag+' '+ca+' / '+cb,e[a+'_bucket5'].eq(ca)&e[b+'_bucket5'].eq(cb),'magnitude_'+tag)
    for state in ['00_月率缺失','01_四项全符合','02_四项全冷','03_四项全热','04_月率冲突','05_月率一致同比反向','06_月率双冷其余','07_月率双热其余','08_总体月率中性核心意外','09_核心月率中性总体意外','10_其他混合']:
        add('joint_'+state,state,e.joint_exclusive.eq(state),'joint_exclusive')
    h=e.headline_mom_surprise_pp;c=e.core_mom_surprise_pp;hy=e.headline_yoy_surprise_pp;cy=e.core_yoy_surprise_pp
    r=e.btc_return_15m;strong=r.abs().ge(.003-1e-12)
    add('all_inline','四项全部符合',(e[[k+'_sign' for k in FIELDS]]==0).all(axis=1),'joint_overlap')
    add('all_cold','四项全部偏冷',(e[[k+'_sign' for k in FIELDS]]<0).all(axis=1),'joint_overlap')
    add('all_hot','四项全部偏热',(e[[k+'_sign' for k in FIELDS]]>0).all(axis=1),'joint_overlap')
    add('mom_yoy_all_cold','同比双冷且月率双冷',(h<0)&(c<0)&(hy<0)&(cy<0),'joint_overlap')
    add('mom_yoy_all_hot','同比双热且月率双热',(h>0)&(c>0)&(hy>0)&(cy>0),'joint_overlap')
    add('yoy_cold_mom_hot','同比双冷但月率双热',(hy<0)&(cy<0)&(h>0)&(c>0),'joint_overlap')
    add('yoy_hot_mom_cold','同比双热但月率双冷',(hy>0)&(cy>0)&(h<0)&(c<0),'joint_overlap')
    for s,name in [(-1,'cold'),(1,'hot')]:
        dual=e.headline_mom_sign.eq(s)&e.core_mom_sign.eq(s)
        add('mom_dual_'+name,'双月率'+LABELS[s],dual,'extreme')
        add('mom_dual_mild_'+name,'双月率温和'+LABELS[s],dual&h.abs().eq(.1)&c.abs().eq(.1),'extreme')
        add('mom_dual_extreme_'+name,'双月率暴'+('冷' if s<0 else '热'),dual&h.abs().ge(.2-1e-12)&c.abs().ge(.2-1e-12),'extreme')
        add('mom_dual_nonextreme_'+name,'双月率'+LABELS[s]+'未达双暴',dual&~(h.abs().ge(.2-1e-12)&c.abs().ge(.2-1e-12)),'extreme')
        add('core_extreme_head_not_'+name,'核心月率暴'+('冷' if s<0 else '热')+'，总体中性或相反',e.core_mom_sign.eq(s)&c.abs().ge(.2-1e-12)&e.headline_mom_sign.isin([0,-s]),'extreme')
        add('head_extreme_core_inline_'+name,'总体月率暴'+('冷' if s<0 else '热')+'，核心符合',e.headline_mom_sign.eq(s)&h.abs().ge(.2-1e-12)&c.eq(0),'extreme')
        add('yoy_dual_extreme_'+name,'双同比暴'+('冷' if s<0 else '热'),e.headline_yoy_sign.eq(s)&e.core_yoy_sign.eq(s)&hy.abs().ge(.2-1e-12)&cy.abs().ge(.2-1e-12),'extreme')
    aligned_hy=hy.notna()&hy.ne(0)&(np.sign(r)==-np.sign(hy))
    aligned_cm=c.notna()&c.ne(0)&(np.sign(r)==-np.sign(c))
    masks={
        'H1_mild':strong&aligned_hy&hy.abs().eq(.1),
        'H1_big':strong&aligned_hy&hy.abs().ge(.2-1e-12),
        'H2_core_mild_cold_up':(c==-.1)&r.ge(.003-1e-12),
        'H2_core_big_cold_up':c.le(-.2+1e-12)&r.ge(.003-1e-12),
        'H3_dual_extreme_hot_down':h.ge(.2-1e-12)&c.ge(.2-1e-12)&r.le(-.003+1e-12),
        'H3_dual_other_hot_down':(h>0)&(c>0)&~(h.ge(.2-1e-12)&c.ge(.2-1e-12))&r.le(-.003+1e-12),
        'H4_hy_inline_up':hy.eq(0)&r.ge(.003-1e-12),
        'H4_hy_cold_up':(hy<0)&r.ge(.003-1e-12),
        'H4_all_inline_up':(e[[k+'_sign' for k in FIELDS]]==0).all(axis=1)&r.ge(.003-1e-12),
        'H5_hy_contrarian':strong&hy.notna()&hy.ne(0)&~aligned_hy,
        'H5_hy_aligned':strong&aligned_hy,
        'H5_cm_contrarian':strong&c.notna()&c.ne(0)&~aligned_cm,
        'H5_cm_aligned':strong&aligned_cm,
        'strong_all':strong,
        'strong_up':r.ge(.003-1e-12),
        'strong_down':r.le(-.003+1e-12),
        'strong_up05':r.ge(.005-1e-12),
        'strong_down05':r.le(-.005+1e-12),
        'A_strict_monthly':strong&aligned_cm&(np.sign(h)==np.sign(c))&(h!=0),
        'B_strict_core':strong&aligned_cm,
    }
    for key,m in masks.items():add(key,key,m,'hypothesis' if key.startswith('H') else 'trading')
    for k in FIELDS:
        for cls in ['暴冷','小幅偏冷','小幅偏热','暴热']:
            add(k+'_'+cls+'_strong_aligned',k+' '+cls+' 强首波顺数据',e[k+'_bucket5'].eq(cls)&strong&np.sign(r).eq(-e[k+'_sign']),'extreme_signal')
    for k in ['headline_mom','headline_yoy','core_yoy']:
        for cls in ['暴冷','小幅偏冷','符合预期','小幅偏热','暴热','缺失']:
            add('H2_'+k+'_'+cls,'H2 '+k+' '+cls,masks['H2_core_mild_cold_up']&e[k+'_bucket5'].eq(cls),'control')
    for k in ['headline_yoy','core_mom']:
        for s in [-1,1]:
            add('H5_'+k+'_sign_'+str(s)+'_contrarian',k+' '+LABELS[s]+' 逆数据强首波',strong&e[k+'_sign'].eq(s)&np.sign(r).eq(s),'control')
            add('H5_'+k+'_sign_'+str(s)+'_aligned',k+' '+LABELS[s]+' 顺数据强首波',strong&e[k+'_sign'].eq(s)&np.sign(r).eq(-s),'control')
    for s in [-1,0,1]:
        add('H1_cm_control_'+str(s),'H1核心月率相对总体 '+str(s),masks['H1_mild']&(e.core_mom_sign*e.headline_yoy_sign).eq(s),'control')
    for k in ['core_yoy','headline_mom']:
        for relation in ['same','inline','opposite']:
            m=e[k+'_sign'].eq(e.headline_yoy_sign) if relation=='same' else e[k+'_sign'].eq(0) if relation=='inline' else e[k+'_sign'].eq(-e.headline_yoy_sign)
            add('H1_'+k+'_'+relation,'H1 '+k+' '+relation,masks['H1_mild']&m,'control')
    for cls in ['暴冷','小幅偏冷','符合预期','小幅偏热','暴热','缺失']:
        add('H4_cm_'+cls,'H4总体同比中性强涨，核心月率'+cls,masks['H4_hy_inline_up']&e.core_mom_bucket5.eq(cls),'control')
    return groups

FLAGS=['keep','new_extreme_touch','new_extreme_end','fade50_touch','fade100_touch','fade50_end','fade100_end','reverse5_touch','reverse5_end','up_then_down_end','down_then_up_end','post_reverse_follow_through','gross_win','net_win']

def summarize_groups(e):
    groups=make_groups(e);out=[];members=[]
    for key,obj in groups.items():
        t=e[obj['mask']];dates=';'.join(t.date)
        for d in t.date:members.append({'group_key':key,'family':obj['family'],'group_label':obj['label'],'date':d})
        for h in HORIZONS:
            x=t[f'btc_return_{h}m'].dropna();row={'group_key':key,'family':obj['family'],'label':obj['label'],'horizon_min':h,'events_n':len(t),'valid_n':len(x),'missing_n':len(t)-len(x),'low_confidence_n_lt10':len(x)<10,'dates':dates,'strong15_n':int(t.strong_first_03.sum()),'zero_return_count':int(x.eq(0).sum())}
            row.update(rate(x.gt(0),'up'));row.update(rate(x.lt(0),'down'));row.update(desc(x,'release_return'))
            if h>15:
                for flag in FLAGS:row.update(rate(t[f'{flag}_{h}m'],flag))
                row.update(desc(t[f'net_return_{h}m'],'momentum_net24'))
                # Conditional, not unconditional, up-then-down / down-then-up denominators.
                for sign,label in [(1,'first_up_reversed_end'),(-1,'first_down_reversed_end')]:
                    sub=t.loc[t.btc_first_direction.eq(sign),f'reverse5_end_{h}m'];row.update(rate(sub,label))
            out.append(row)
    s=pd.DataFrame(out);save(s,'group_windows.csv');save(pd.DataFrame(members),'group_memberships.csv')
    extreme=[]
    for key,obj in groups.items():
        if obj['family'] not in ['extreme','extreme03','extreme_signal'] and not (obj['family']=='single' and key.endswith(('_暴热','_暴冷'))):continue
        for _,r in e[obj['mask']].iterrows():extreme.append({'record_type':'event','group_key':key,'group_label':obj['label'],**r.to_dict()})
        for _,r in s[(s.group_key==key)&s.horizon_min.isin([15,60,240])].iterrows():extreme.append({'record_type':'summary',**r.to_dict()})
    save(pd.DataFrame(extreme),'extreme_research.csv')
    tests=[]
    for fam in ['matrix_mom','matrix_yoy','matrix_hy_cm']:
        for h in [15,60,240]:
            for key,obj in groups.items():
                if obj['family']!=fam or key.endswith('missing'):continue
                a=e.loc[obj['mask'],f'btc_return_{h}m'];b=e.loc[~obj['mask'],f'btc_return_{h}m']
                tests.append({'family':'matrix_exploratory','group_key':key,'horizon_min':h,**mean_test(a,b,key+str(h))})
    tt=pd.DataFrame(tests);tt['q']=bh(tt.p);save(tt,'matrix_exploratory_tests.csv')
    print('groups',len(groups),'window rows',len(s),flush=True)
    return groups,s

if __name__=='__main__':summarize_groups(pd.read_csv(OUT/'events_four.csv'))
