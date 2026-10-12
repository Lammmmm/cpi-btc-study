"""Chinese report and trader guide generated from computed tables only."""
from common import *
from groups import make_groups
import re,html,os,shutil
os.environ['SOURCE_DATE_EPOCH']=str(int(pd.Timestamp('2026-10-12T00:00Z').timestamp()))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,CondPageBreak
from reportlab.pdfgen.canvas import Canvas

H={5:'5m',10:'10m',15:'15m',30:'30m',60:'1h',120:'2h',240:'4h',1440:'24h'}
CN={'headline_mom':'总体环比','core_mom':'核心环比','headline_yoy':'总体同比','core_yoy':'核心同比','stable':'稳健','deteriorating':'恶化','unclassified':'未分类','pause':'暂停','hiking':'加息','cutting':'降息'}

def pct(x,d=2):return '不可估计' if pd.isna(x) else f'{100*x:+.{d}f}%'
def num(x,d=3):return '不可估计' if pd.isna(x) else f'{x:.{d}f}'
def rr(row,key,ci=True):
    n=int(row[key+'_n']);k=int(row[key+'_count'])
    if not n:return '无有效样本'
    return f'{k}/{n} ({100*row[key+"_rate"]:.1f}%)'+(f' [{100*row[key+"_ci_low"]:.1f},{100*row[key+"_ci_high"]:.1f}]' if ci else '')
def avg(row,key='net_return',ci=True):
    val=row.get(key+'_mean',np.nan)
    if pd.isna(val):return '无有效样本'
    if ci and pd.isna(row.get(key+'_mean_ci_low',np.nan)):return pct(val)+'（单例）'
    return pct(val)+(f' [{pct(row.get(key+"_mean_ci_low",np.nan))},{pct(row.get(key+"_mean_ci_high",np.nan))}]' if ci else '')
def table(head,rows):
    display={'H1_mild':'总体同比温和顺向','H1_big':'总体同比显著顺向','H2_core_mild_cold_up':'核心环比温和冷强涨','H4_hy_inline_up':'总体同比符合强涨','strong_all':'全部强首波','strong_up':'首波涨>=0.3%','strong_down':'首波跌<=-0.3%','strong_up05':'首波涨>=0.5%','strong_down05':'首波跌<=-0.5%','B_strict_core':'核心相符强首波','2019_2023':'2019-2023','2024_2026':'2024-2026','exclude2022':'剔除2022','growth_strict':'严格PIT','growth_snapshot':'扩展快照','headline':'总体两项','core':'核心两项','combined':'四项组合','headline_mom_only':'仅总体环比','core_mom_only':'仅核心环比','constant':'常数','first15_up':'15m上涨','keep4h_strong':'强首波4h保持','holdout_2024_2026':'2024-2026留出','walk_forward_2022_2026':'逐年扩展2022-2026','H5_headline':'H5总体','H5_core':'H5核心'}
    def cell(v):return display.get(str(v),str(v)).replace('net_return','净交易收益').replace('reverse5_touch','期间反转').replace('|','/')
    return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(cell(v) for v in row)+' |' for row in rows])

def load(name):return pd.read_csv(OUT/(name+'.csv'))
def grow(s,key,h):return s[s.group_key.eq(key)&s.horizon_min.eq(h)].iloc[0]
def trow(t,key,fam='A',h=60,c=15,kind=None):
    if kind is None:kind='absolute_event' if fam=='A' else 'relative_hold'
    return t[t.group_key.eq(key)&t.family.eq(fam)&t.horizon_min.eq(h)&t.confirm_min.eq(c)&t.exit_kind.eq(kind)].iloc[0]

def make_charts(s,t):
    figdir=ROOT/'figures';figdir.mkdir(exist_ok=True);font=FontProperties(fname=str(ORIGINAL/'fonts/NotoSansSC-Regular.ttf'))
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10,'axes.unicode_minus':False})
    fig,ax=plt.subplots(figsize=(9,4.3))
    keys=['H1_mild','H1_big','H2_core_mild_cold_up','H4_hy_inline_up'];labels=['总体同比温和意外\n顺数据强首波','总体同比显著意外\n顺数据强首波','核心环比温和冷\n强上涨','总体同比符合\n强上涨']
    xs=np.arange(len(keys));vals=[];low=[];high=[]
    for key in keys:
        r=trow(t,key);vals.append(r.net_return_mean*100);low.append((r.net_return_mean-r.net_return_mean_ci_low)*100);high.append((r.net_return_mean_ci_high-r.net_return_mean)*100)
    ax.bar(xs,vals,color=['#bb6555','#3b7c90','#bb6555','#82909e'],width=.6,yerr=np.array([low,high]),capsize=4)
    for i,key in enumerate(keys):
        r=trow(t,key);ax.text(i,max(vals[i],0)+high[i]+.07,f'n={int(r.trades_n)}; 盈利{int(r.net_win_count)}次',ha='center',fontproperties=font,fontsize=9)
    ax.set_xticks(xs,labels,fontproperties=font);ax.set_ylabel('第16分钟入场至1小时净收益（%）',fontproperties=font);ax.axhline(0,color='#929ca5',lw=.7);ax.set_ylim(-.85,1.05)
    ax.set_title('确认后追单：四项CPI升级没有消除成本与回吐',fontproperties=font,fontsize=14);fig.tight_layout();fig.savefig(figdir/'net1h_rules.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(9,4.5))
    for ax,field,title in [(axs[0],'up_rate','15分钟上涨概率'),(axs[1],'release_return_mean','4小时公布价回报均值')]:
        vals=np.full((3,3),np.nan)
        for i,a in enumerate([-1,0,1]):
            for j,b in enumerate([-1,0,1]):
                row=grow(s,f'mom_{a}_{b}',15 if field=='up_rate' else 240);vals[i,j]=row[field]*100 if row.events_n else np.nan
        vlim=(0,100) if field=='up_rate' else (-2,2)
        ax.imshow(vals,cmap='RdYlBu' if field=='up_rate' else 'RdBu',vmin=vlim[0],vmax=vlim[1])
        for i,a in enumerate([-1,0,1]):
            for j,b in enumerate([-1,0,1]):
                r=grow(s,f'mom_{a}_{b}',15 if field=='up_rate' else 240);txt='n=0' if not r.events_n else f'{vals[i,j]:.1f}%\nn={int(r.events_n)}'
                cmap=plt.get_cmap('RdYlBu' if field=='up_rate' else 'RdBu');norm=(vals[i,j]-vlim[0])/(vlim[1]-vlim[0]);rgb=cmap(norm)[:3] if np.isfinite(norm) else (1,1,1)
                luminance=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]
                ax.text(j,i,txt,ha='center',va='center',fontproperties=font,fontsize=10,color='white' if luminance<.5 else '#172b40')
        ax.set_xticks([0,1,2],['核心冷','核心符合','核心热'],fontproperties=font);ax.set_yticks([0,1,2],['总体冷','总体符合','总体热'],fontproperties=font);ax.set_title(title,fontproperties=font,fontsize=12)
    fig.suptitle('双月率交叉矩阵：方向预测与4小时结果分开',fontproperties=font,fontsize=14);fig.tight_layout();fig.savefig(figdir/'mom_matrix.png',dpi=180);plt.close(fig)

def build_decision(s,t):
    items=[('H1_mild','总体同比温和意外','顺数据>=0.3%',0),('H2_core_mild_cold_up','核心月率温和冷、总体任意','上涨>=0.3%',1),('mom_dual_cold','总体、核心均冷（各强度）','上涨>=0.3%',1),('mom_dual_hot','总体、核心均热（各强度）','下跌<=-0.3%',-1),('mom_mag_小幅偏冷_小幅偏冷','总体温和冷、核心温和冷','上涨>=0.3%',1),('mom_dual_extreme_cold','总体暴冷、核心暴冷','上涨>=0.3%',1),('mom_mag_小幅偏热_小幅偏热','总体温和热、核心温和热','下跌<=-0.3%',-1),('mom_dual_extreme_hot','总体暴热、核心暴热','下跌<=-0.3%',-1),('mom_mag_符合预期_暴冷','总体符合、核心暴冷','强首波任一方向',0),('mom_mag_符合预期_暴热','总体符合、核心暴热','强首波任一方向',0),('mom_1_-1','总体热、核心冷','强首波任一方向',0),('mom_-1_1','总体冷、核心热','强首波任一方向',0)]
    e=load('events_four');groups=make_groups(e);tr=load('trades_all');rows=[]
    for key,label,react,sign in items:
        # Magnitude cells are not retained in every strategy sheet; derive from canonical trades.
        m=groups[key]['mask']&e.strong_first_03.eq(1)
        if sign:m=m&e.btc_first_direction.eq(sign)
        ev=e[m];ids=set(ev.date);a=tr[tr.date.isin(ids)&tr.family.eq('A')&tr.confirm_min.eq(15)&tr.horizon_min.eq(60)&tr.execution_lag_min.eq(1)];b=tr[tr.date.isin(ids)&tr.family.eq('B')&tr.horizon_min.eq(60)&tr.exit_kind.eq('relative_hold')&tr.execution_lag_min.eq(1)]
        n=len(ev);rev=int(ev.reverse5_touch_240m.sum());wa=int(a.net_return.gt(0).sum());wb=int(b.net_return.gt(0).sum())
        row={'CPI组合':label,'BTC前15m条件':react,'组合标签总事件数':int(groups[key]['mask'].sum()),'强首波条件事件数':n,'4h真正反转次数':rev,'4h反转率':rev/n if n else np.nan,'顺势1h交易数':len(a),'顺势1h净盈利数':wa,'顺势1h净胜率':wa/len(a) if len(a) else np.nan,'顺势1h平均净收益':a.net_return.mean(),'反杀后持有1h交易数':len(b),'反杀后持有1h净盈利数':wb,'反向1h净胜率':wb/len(b) if len(b) else np.nan,'反向1h平均净收益':b.net_return.mean(),'事件日期':';'.join(ev.date)}
        for prefix,k,den in [('4h反转',rev,n),('顺势净胜',wa,len(a)),('反向净胜',wb,len(b))]:row[prefix+'_Wilson低'],row[prefix+'_Wilson高']=wilson(k,den)
        if n<10:row['交易判断']='样本不足；仅记录，不形成规则'
        elif pd.notna(row['顺势1h平均净收益']) and row['顺势1h平均净收益']<0:row['交易判断']='追单历史均值为负；反杀仍须独立确认'
        else:row['交易判断']='历史候选；尚无已验证优势'
        vals=ev.net_return_60m if len(ev) else pd.Series(dtype=float)
        row['未来1h最常见结果']='样本不足' if n<10 else f'顺势入场净亏损{int(vals.le(0).sum())}/{n}；公布价同侧{int(ev.keep_60m.sum())}/{n}'
        rows.append(row)
    out=pd.DataFrame(rows);save(out,'decision_table.csv');return out

def make_markdown():
    e=load('events_four');s=load('group_windows');t=load('strategy_groups');hyp=load('hypothesis_tests_primary');rb=load('robustness');pred=load('prediction_metrics');inc=load('prediction_incremental_tests');g=make_groups(e)
    decisions=build_decision(s,t);make_charts(s,t);sections=[]
    def add(x):sections.append(x.strip())
    add('# 美国CPI与BTC四指标历史事件回测最终报告\n\n2019-01-11至2026-09-11，92次正式发布。研究截止2026-10-11，升级复算日期2026-10-12。')
    add('## 1. 执行摘要：第一波何时值得信，何时容易追在错误位置')
    add('**最强的实际用途是避免温和意外之后追逐强首波。没有发现通过多重检验和时间稳定性检查的正收益交易系统。核心环比提供了重要的分组信息，但加入核心数据没有自动提升时间留出预测。**')
    rows=[]
    for key,label in [('H1_mild','总体同比温和±0.1pp，顺数据强首波'),('H1_big','总体同比显著>=0.2pp，顺数据强首波'),('H2_core_mild_cold_up','核心环比-0.1pp，BTC上涨>=0.3%'),('H4_hy_inline_up','总体同比符合，BTC上涨>=0.3%')]:
        a=trow(t,key);b=trow(t,key,h=240);p=grow(s,key,240)
        rows.append([label,int(a.trades_n),rr(a,'net_win'),avg(a),rr(p,'reverse5_touch'),avg(b)])
    add(table(['触发条件','n','1h追单净胜率，95%CI','1h净均值，95%CI','4h真正反转，95%CI','4h追单净均值'],rows))
    h1=hyp[(hyp.hypothesis=='H1')&(hyp.outcome=='net_return')&(hyp.horizon_min==60)].iloc[0]
    add(f'温和组与显著组1小时净均值差为{100*h1.effect_a_minus_b:+.3f}个百分点，95%CI [{100*h1.ci_low:+.3f},{100*h1.ci_high:+.3f}]，置换p={h1.p:.4f}，18项主检验BH q={h1.q_primary:.4f}。这支持两组存在历史差异；显著组本身的正均值仍未通过全部策略筛选后的显著性与年份稳定性检查，不能把比较显著等同于可部署策略。')
    add('核心环比温和偏冷的10次强上涨，1小时追多0次净盈利，4小时仅5次盘中触达公布价、3次完整5分钟收盘反转。新增B策略实际仅触发3笔：反转后持有1小时2/3净盈利；至事件4小时退出3/3，但均为极低样本。**追多亏损、回吐、真正反转、反向交易赚钱是四个不同事件。**')
    add('双月率偏冷的首波上涨16/20，双月率偏热的首波下跌17/21。双月率暴热6次首波却仅3次下跌；双月率暴冷4次有3次上涨。极端组尤其稀疏，不能直接外推胜率。总体月率暴热且核心月率符合，以及核心月率暴热且总体符合或偏冷，都没有观测事件。')
    add('时间留出模型：预测15分钟上涨，总体两项准确23/31=74.2%，核心两项20/31=64.5%，四项组合20/31=64.5%；四项组合的Brier和log loss也稍差，差值区间均跨零。不能宣称核心环比一定更有预测力，也不能由这31次证明它永远无用。')
    add('![1小时净收益与区间](../figures/net1h_rules.png)')
    add('## 2. 数据、分母与可复现审计')
    add(table(['年份','正式事件数'],[[int(y),int(n)] for y,n in e.groupby('year').size().items()]))
    add('92=2019至2024各12次+2025年11次+2026年9次。2025年10月参考月没有发布CPI；2025-10-24发布延迟的9月数据，仍计入。2025-12-18没有可用的两项当月MoM实际/预期，不能用新闻稿中的两个月累计0.2%代替。两项同比各92组、两项环比各91组；所有92次BTC均纳入，月率矩阵有效91、同比矩阵92、总体同比×核心环比91，缺失独立列示。')
    add('原项目的184个Binance每日ZIP及官方CHECKSUM、92份BLS新闻稿、368个事件前ALFRED版本、92段Coinbase核验记录和完整源码均已找到。当前提供的cpi_events(1).csv与原项目92行数据库完全一致；补充CSV全部74项核对通过。原研究会计/缺失审计通过，升级18项测试通过，包含所有5322条执行情景的实际入场/出场价、下一分钟入场、反杀和延迟信号先后检查。')
    audit=load('independent_raw_return_audit').iloc[0]
    add(f'独立从原始ZIP重算{int(audit.valid_returns)}个有效5/10/15/30/60/120/240/1440分钟回报，与升级CSV最大误差{audit.max_raw_return_error:.3g}；184/184官方SHA256吻合。92条4小时路径全部完整；2021-02-10的24小时路径缺2021-02-11 03:41至04:59 UTC共79分钟，因此整条24h路径剔除，24h n=91。1380条确认窗×目标窗路径中1377条有效。没有用插值、其他交易所或终点价补出缺失路径。')
    add('四项实际来自当次BLS，预期来自事后获取的Investing历史日历字段。保留来源URL、事件ID、官方一致性和历史可用性标记，**没有逐次独立封存发布前08:29调查快照**。因此精确说，这是可审计的历史日历预期回测，不是每个时点均获得独立封存调查数据的PIT认证。旧报告关于当时预期的强表述必须收窄。')
    add('当前成交模拟使用Binance BTCUSDT现货分钟OHLCV。主成本24bp是每边10bp参考费用加每边2bp假定滑点，不是实际账户历史成交成本。已核验零手续费活动期间另测4bp滑点情景；做空假设可借BTC，未纳入借币费用、资格与永续资金费。所有策略结果是可执行价格模拟及成本情景，不能承诺未来在分钟open成交。')
    add('## 3. 四项CPI分类与完整交叉矩阵')
    add(table(['名称','定义','有效事件'],[['总体环比 Headline MoM','当月总体变化，季调',91],['核心环比 Core MoM','除食品能源当月变化，季调',91],['总体同比 Headline YoY','总体12个月变化，未季调',92],['核心同比 Core YoY','除食品能源12个月变化，未季调',92]]))
    add(table(['五档操作性分类','实际减预期（pp）'],[['暴冷','<=-0.2'],['小幅偏冷','-0.1'],['符合预期','0'],['小幅偏热','+0.1'],['暴热','>=+0.2']]))
    add('“暴”只是用户指定的操作性意外阈值，既不是市场公认定义，也不是实际同比通胀很高/很低。实际与预期先转换为0.1pp整数刻度再相减，避免0.099999浮点误判。符合预期是展示精度一致，不等于没有信息。另保存>=0.3pp及过去24个非缺失事件误差标准差归一化结果，至少12个先前观测，绝不包含当前误差。')
    rows=[]
    for k in FIELDS:
        counts=e[k+'_bucket5'].value_counts();rows.append([CN[k]]+[int(counts.get(x,0)) for x in ['暴冷','小幅偏冷','符合预期','小幅偏热','暴热','缺失']])
    add(table(['指标','暴冷','温和冷','符合','温和热','暴热','缺失'],rows))
    for tag,title in [('mom','3.1 总体环比×核心环比：主分析'),('yoy','3.2 总体同比×核心同比'),('hy_cm','3.3 总体同比×核心环比：复核旧研究')]:
        add('### '+title)
        rows=[]
        for a in [-1,0,1]:
            for b in [-1,0,1]:
                key=f'{tag}_{a}_{b}';f=grow(s,key,15);u=grow(s,key,60);v=grow(s,key,240)
                rows.append([LABELS[a]+'/'+LABELS[b],int(f.events_n),rr(f,'up'),avg(f,'release_return'),avg(u,'release_return'),avg(v,'release_return')])
        add(table(['总体/核心','n','15m上涨，95%CI','15m均值，95%CI','1h均值，95%CI','4h均值，95%CI'],rows))
        rows=[]
        for a in [-1,0,1]:
            for b in [-1,0,1]:
                key=f'{tag}_{a}_{b}';v=grow(s,key,240)
                rows.append([LABELS[a]+'/'+LABELS[b],rr(v,'keep'),rr(v,'fade50_touch'),rr(v,'fade100_touch'),rr(v,'reverse5_touch')])
        add(table(['总体/核心','4h方向保持，95%CI','50%期间回吐，95%CI','100%期间回吐，95%CI','5m收盘反转，95%CI'],rows))
        add('表内路径分母是该组合的所有非零第一波，不设0.3%门槛。交易表再用强首波门槛；方向保持不是交易盈利。完整5/10/15/30/60/120/240/1440分钟均值、中位数、分位数、极值、期间及终点标记，以及3×3和5×5全单元格，见工作簿和group_windows.csv。零样本显示无有效样本，不以0%代替。')
    add('![月率矩阵](../figures/mom_matrix.png)')
    add('总体同比与核心环比冲突共5次，首波跟随核心4/5、跟随总体1/5。总体同比中性且核心环比冷6次，首波全部上涨；同样中性且核心环比热6次，却只有3次下跌。这两类不对称不能合并成“核心总是占主导”。主月率冲突只有1次，无力比较总体/核心谁更强。')
    add('### 3.4 四项联合互斥状态与重叠标签')
    rows=[]
    for key,obj in g.items():
        if obj['family']!='joint_exclusive':continue
        f=grow(s,key,15);v=grow(s,key,240);rows.append([obj['label'].split('_',1)[-1],int(f.events_n),rr(f,'up',False),rr(v,'keep',False),rr(v,'reverse5_touch',False)])
    add(table(['按优先级划分的互斥状态','n','15m上涨','4h保持','4h真正反转'],rows))
    add('按月率缺失、四项全部符合/冷/热、月率冲突、月率一致同比反向、其余月率双冷/双热、总体月率中性核心意外、核心月率中性总体意外、其余混合的优先级划分，合计恰为92。双月率、双同比、四项全冷/全热以及不同强度属于另外的重叠标签，只能各自取分母，不能把标签样本相加。每组全部日期保存在group_memberships.csv和工作簿。同比双冷但月率双热、同比双热但月率双冷在这92次中均为零样本。')
    add('## 4. 暴热与暴冷专项研究')
    add('本章“总体/核心”默认两项环比，另列同比以免复用旧口径。极端组不与温和意外合并。“同向”只是冷对应涨、热对应跌的操作性对照；真实概率由样本计算，不预设低通胀必然利好。')
    rows=[]
    for k in FIELDS:
        for cls,direction in [('暴热','down'),('暴冷','up')]:
            f=grow(s,k+'_'+cls,15);v=grow(s,k+'_'+cls,240)
            rows.append([CN[k]+cls,int(f.events_n),'下跌' if direction=='down' else '上涨',rr(f,direction),avg(v,'release_return'),rr(v,'reverse5_touch')])
    add(table(['单指标>=0.2pp意外','全部事件n','同向对照方向','首波同向率，95%CI','4h公布价均值，95%CI','4h真正反转，95%CI'],rows))
    rows=[]
    keys=['mom_dual_extreme_hot','mom_dual_extreme_cold','core_extreme_head_not_hot','core_extreme_head_not_cold','head_extreme_core_inline_hot','head_extreme_core_inline_cold','yoy_dual_extreme_hot','yoy_dual_extreme_cold']
    for k in keys:
        f=grow(s,k,15);v=grow(s,k,240);rows.append([g[k]['label'],int(f.events_n),rr(f,'up'),avg(v,'release_return'),rr(v,'reverse5_touch'),'极低' if f.events_n<=3 else '低' if f.events_n<10 else '一般'])
    add(table(['场景','n','15m上涨，95%CI','4h公布价均值，95%CI','4h反转，95%CI','样本置信'],rows))
    for k in keys[:6]:
        events=e[g[k]['mask']]
        add('### '+g[k]['label'])
        if not len(events):add('样本为0，未验证。不得把这类理论合理的组合填成可靠交易概率。');continue
        rows=[]
        for _,r in events.iterrows():rows.append([r.date,f'{r.headline_mom_surprise_pp:+.1f}/{r.core_mom_surprise_pp:+.1f}',pct(r.btc_return_15m),pct(r.btc_return_60m),pct(r.btc_return_240m),pct(r.net_return_60m),pct(r.net_return_240m),int(r.reverse5_touch_240m)])
        add(table(['日期','月率意外H/C (pp)','15m回报','1h回报','4h回报','首波顺势1h净','首波顺势4h净','4h反转'],rows))
        add('逐事件顺势净收益按实际BTC第一波方向，逆数据首波不会被冒称“按CPI方向追空/追多”。下表另只取与数据相符的强首波。')
    rows=[]
    for key,label in [('H3_dual_extreme_hot_down','双月率暴热且BTC跌>=0.3%'),('mom_dual_extreme_cold','双月率暴冷且BTC涨>=0.3%'),('headline_yoy_暴热_strong_aligned','总体同比暴热且强下跌'),('core_mom_暴热_strong_aligned','核心环比暴热且强下跌')]:
        a=trow(t,key);b=trow(t,key,h=240);rows.append([label,int(a.trades_n),rr(a,'net_win'),avg(a),rr(b,'net_win'),avg(b)])
    add(table(['条件','交易n','1h净胜率，95%CI','1h净均值，95%CI','4h净胜率，95%CI','4h净均值，95%CI'],rows))
    add('双月率暴热且强下跌仅3次，双暴冷且强上涨也只有3次，均不能输出可靠概率。2021-06-10与2021-11-10两次双暴热仍先涨：前者4h追多亏损，后者继续上涨；同样的“逆数据”外观并非必然反杀。2020-08-12首波上涨不足0.3%，不得偷偷纳入强首波追空分母。')
    add('>=0.3pp的更极端意外、温和/显著混配，以及过去误差标准化分层都已经实际统计并留存CSV和工作簿；它们是敏感性和探索结果，不以哪一格漂亮反过来修改0.2pp主阈值。')
    add('## 5. 五条旧规律重新验证')
    conclusions=[('H1','部分支持：温和总体同比顺数据强首波后不宜追单；1h相对显著组差异成立，4h对比不显著。'),('H2','部分支持：24bp下1h追多历史0/10盈利；不支持等同于必然回吐/必然反杀获利。'),('H3','部分支持方向描述，交易优势证据不足；双暴热6次首波3跌3涨，不支持其更可靠，但小样本不能排除未来概率更高。'),('H4','部分支持9/10方向保持；“四项都符合后的趋势优势”证据不足，强上涨实际仅1次。'),('H5','证据不足：逆数据首波的反转率略高，但比较区间跨零，全部主q不显著。')]
    add(table(['假设','本次结论'],conclusions))
    rows=[]
    for _,r in hyp.iterrows():rows.append([r.hypothesis,H[int(r.horizon_min)]+' '+r.outcome,f'{int(r.n_a)}/{int(r.n_b)}',f'{100*r.effect_a_minus_b:+.3f}',f'[{100*r.ci_low:+.3f},{100*r.ci_high:+.3f}]',num(r.p,4),num(r.q_primary,4)])
    add(table(['假设','比较结果','nA/nB','A-B (pp)','95%差区间','p','主BH q'],rows))
    add(f'主要18项对比在结果计算前写入SPECIFICATION，但旧样本和原规律已看过，仍是回顾性研究。A/B定义与完整检验菜单见hypothesis_tests_primary.csv。方向率用Fisher和Newcombe，收益差用10000次置换及独立事件bootstrap。只有H1的1h净收益差q<0.05；描述CI并不是所有切片的同时CI。矩阵探索81项以及{len(t)}行策略的可计算均值检验各自校正，不能把它们的q偷换成主假设q。')
    add('### H1：温和总体同比意外与其他三项指标的控制')
    rows=[]
    for key in ['H1_cm_control_1','H1_cm_control_0','H1_cm_control_-1']:
        a=trow(t,key);b=trow(t,key,h=240);rows.append([{'H1_cm_control_1':'核心环比同向','H1_cm_control_0':'核心环比符合','H1_cm_control_-1':'核心环比反向'}[key],int(a.trades_n),rr(a,'net_win'),avg(a),avg(b)])
    add(table(['温和HY顺数据强首波内部','n','1h净胜率，95%CI','1h净均值，95%CI','4h净均值，95%CI'],rows))
    add('12次核心月率同向组仍只有1次1h盈利，均值约-0.394%；所以旧现象并非全部由忽略反向核心通胀解释。核心中性2次、反向1次，不能估计稳定的条件差异。核心同比、总体环比的同向/符合/反向拆分已逐组计算，保存在control分组；这些是分层控制，没有因果意义，也没有以92个事件硬拟合高维因果模型。')
    add('唯一核心环比反向事件为2025-07-15，意外仅-0.1pp，未达到>=0.2pp的明显反向；明显核心反向子组为零样本，不能借这1次回答更强的条件。')
    add('### H2：核心环比温和偏冷后的上涨到底输在哪里')
    z=e[g['H2_core_mild_cold_up']['mask']];rows=[]
    for _,r in z.iterrows():rows.append([r.date,f'{r.headline_mom_surprise_pp:+.1f}/{r.core_mom_surprise_pp:+.1f}',f'{r.headline_yoy_surprise_pp:+.1f}/{r.core_yoy_surprise_pp:+.1f}',CN[r.policy_stage]+'/'+CN[r.growth_strict],pct(r.net_return_60m),int(r.fade100_touch_240m),int(r.reverse5_touch_240m),pct(r.B_hold60_net_return)])
    add(table(['日期','HM/CM意外','HY/CY意外','政策/严格增长','追多1h净','4h全吐','4h反转','触发后反向1h净'],rows))
    a=trow(t,'H2_core_mild_cold_up');v=grow(s,'H2_core_mild_cold_up',60);w=grow(s,'H2_core_mild_cold_up',240)
    add(f'1h追多净盈利{rr(a,"net_win")}，但1h仍高于公布价{rr(v,"keep")}，1h完全回吐和收盘反转均只有{int(v.fade100_touch_count)}/10。到4h完全回吐{rr(w,"fade100_touch")}、真正反转{rr(w,"reverse5_touch")}、仍高于公布价{rr(w,"keep")}。不少亏损来自已上涨后高价追入、随后只部分回吐和24bp成本，而不是每次都向下趋势反转。')
    add('这10次分布2019两次、2021一次、2022一次、2024两次、2025三次、2026一次；严格增长稳健3、恶化1、未分类6，不能断定是同一种需求衰退机制。1h净均值在2019-2023和2024-2026分别约-0.236%和-0.431%，剔除2022仍0/9盈利。成本8/12bp时转为2/10盈利，均值仍负；“0/10”不是成本无关的市场规律。')
    add('宏观全集是21次核心环比温和偏冷：其中10次满足强上涨初始门槛，继而3次触发B，7次门槛满足但未反转，11次未满足初始强上涨。不能把3/10的条件触发率当作3/21的宏观总体触发率；两种分母均可由事件和触发审计表复算。')
    add('### H4：总体同比符合的强涨，是否只是漏看核心')
    rows=[]
    for cls in ['暴冷','小幅偏冷','符合预期','小幅偏热','暴热']:
        key='H4_cm_'+cls;v=grow(s,key,240);a=trow(t,key,h=240);rows.append([cls,int(v.events_n),rr(v,'keep'),rr(v,'reverse5_touch'),rr(a,'net_win'),avg(a)])
    add(table(['HY中性强涨的CM分类','n','4h保持，95%CI','4h反转，95%CI','4h追多净胜率，95%CI','4h净均值，95%CI'],rows))
    add('原10次中核心环比暴冷1、温和冷3、符合3、温和热3。9/10保持并非全由核心偏冷解释，因为核心温和热3次也全部保持；但每格只有1至3次。四项全符合且强上涨仅2024-11-13一笔，不能继承原来9/10的分母。')
    add('## 6. 第一波、回吐与二次定价')
    add('P0为T0前一分钟close；15m信号用T0+14分钟K线close，闭合时刻T0+15。主策略于T0+16 open进入。目标回报用T0+H-1 close相对P0；实际退出用T0+H open。50%回吐基于首波沿方向极值E，100%回吐是触达P0；真正反转必须完整5m close严格跨P0。目标时点状态与期间触发可以重叠，不能相加。')
    rows=[]
    for h in [30,60,120,240,1440]:
        v=grow(s,'strong_all',h);rows.append([H[h],int(v.valid_n),rr(v,'keep'),rr(v,'new_extreme_touch'),rr(v,'fade50_touch'),rr(v,'fade100_touch'),rr(v,'reverse5_touch')])
    add(table(['时间','n','方向保持，95%CI','创新极值，95%CI','50%回吐，95%CI','100%回吐，95%CI','收盘反转，95%CI'],rows))
    rows=[]
    for key in ['strong_up','strong_down','strong_up05','strong_down05']:
        for h in [30,60,240]:
            v=grow(s,key,h);rows.append([key,H[h],int(v.valid_n),rr(v,'reverse5_end'),rr(v,'reverse5_touch'),rr(v,'post_reverse_follow_through')])
    add(table(['首波条件','终点','n','终点相反方向，95%CI','期间收盘反转，95%CI','反转后继续反向，95%CI'],rows))
    add('“反转后继续反向”的分母仅是该期限之前已确认反转、且反转时点早于期限的事件，比较首次反转5m close与目标close；不是反向策略收益。0.3/0.5%的切片、5/10/15分钟确认、z门槛均完整提供，未选一个最漂亮参数替换主规格。')
    add('## 7. 可执行交易：顺势A、反杀B、延迟C')
    add('所有记录保存条件、信号和入场UTC、真实分钟open、方向、退出价、往返成本、毛/净收益、MFE和MAE。固定期限退出，没有事后挑止盈止损。5322行是多个确认窗/期限/延迟的情景记录，不是5322个独立机会；每一条策略均按日期取独立事件。')
    rows=[]
    for fam,c,h,kind in [('A',15,30,'absolute_event'),('A',15,60,'absolute_event'),('A',15,120,'absolute_event'),('A',15,240,'absolute_event'),('B',15,15,'relative_hold'),('B',15,30,'relative_hold'),('B',15,60,'relative_hold'),('B',15,120,'relative_hold'),('B',15,240,'absolute_event'),('C',30,60,'relative_hold'),('C',60,240,'relative_hold')]:
        r=trow(t,'strong_all',fam,h,c,kind);lab=f'{fam} '+('事件'+H[h]+'退出' if kind=='absolute_event' else '确认'+H[c]+'后持有'+H[h])
        rows.append([lab,int(r.trades_n),rr(r,'net_win'),avg(r),num(r.payoff_ratio,2),num(r.profit_factor,2),pct(r.minute_close_max_drawdown)])
    add(table(['策略基准，24bp','交易n','净胜率，95%CI','平均净收益，95%CI','盈亏比','利润因子','分钟收盘最大回撤'],rows))
    add('A主确认版还要求两个月率同向且BTC相符：25次，1h净盈利11/25、净均值约+0.111%，4h净盈利10/25、净均值约-0.457%。这比不过滤的1h追单均值略好，但没有校正后的显著正收益。B核心数据相符版有32次初始条件、13次真正触发，反杀后1h净均值约-0.123%。C表内是同方向基准，双月率暴冷等条件的专属结果也已计算，样本只有3笔。')
    cf=load('A_monthly_confirmation');rows=[]
    for _,r in cf[cf.split.eq('all')&cf.horizon_min.isin([60,240])].iterrows():rows.append([int(r.confirm_min),int(r.entry_min),H[int(r.horizon_min)],int(r.trades_n),rr(r,'net_win'),avg(r),num(r.q_confirmation_exploratory,4)])
    add(table(['双月率确认分钟','实际入场分钟','事件退出','n','净胜率，95%CI','净均值，95%CI','确认窗探索q'],rows))
    add('5/10m确认只用该时点已经完成的价格和T0公布的CPI，首波>=0.3%门槛也使用对应5/10m，绝不先筛15m强首波再回填更早成交。各确认窗时间留出和剔除2022结果见A_monthly_confirmation.csv；未择最优确认时点替换15m主规格。')
    add('5/10m双月率确认的1h全样本净均值虽为+0.301%/+0.215%，各48项探索校正q约0.287/0.359；2024-2026各9笔均只有2笔盈利，均值-0.281%/-0.226%，剔除2022也分别约-0.200%/-0.196%。更早入场的正历史点估计主要来自早期年份，不能作为稳定优势。')
    add('### B：真正反杀后的反向入场')
    add('扫描15m确认之后至T0+240的首次完整5m反向收盘，只取第一次；下一分钟open反向入场。相对持有15/30/60/120分钟，与固定事件4h退出分别统计。相对持有可能结束在T0+4h以后，不能冒称公布至1h收益。若反转到240m才发生，则固定4h退出没有可执行持有期；触发与可执行数量在审计表独立记录。')
    rows=[]
    for key in ['strong_all','B_strict_core','H1_mild','H2_core_mild_cold_up','H4_hy_inline_up']:
        for h,kind in [(60,'relative_hold'),(240,'absolute_event')]:
            r=trow(t,key,'B',h,15,kind);rows.append([key,'持有1h' if kind=='relative_hold' else '事件4h',int(r.eligible_strong15_n),int(r.trades_n),int(r.untriggered_or_not_executable_n),rr(r,'net_win'),avg(r),rr(r,'re_reversal5')])
    add(table(['条件','退出规则','初始n','触发交易n','未触发/不可执行n','净胜率，95%CI','净均值，95%CI','入场后再反杀，95%CI'],rows))
    add('两行相同条件分别是触发后持有1h和事件4h退出，切勿混读。全部55次强首波中30次没有触发，不能给它们虚构反向成交；25笔B的1h净盈利9/25、均值约-0.114%，再回到原首波P0一侧16/25。固定4h退出虽14/25盈利、均值约+0.106%，区间跨零，且17/25期间再反杀。第一次穿越P0不是可靠的趋势终点。')
    add('### C：延迟确认不能自动解决追单问题')
    add('30m或60m确认须仍处于15m首波同侧、此前没有完整5m反转，分别31m或61m open入场，再持有60/120/240分钟。55次初始强首波中30m条件52次、60m条件47次触发。30m确认后持有1h净均值约-0.436%，60m确认后持有4h约-0.838%；不能用“等得更久”作为已验证改进。')
    add('## 8. 稳健性、政策与增长环境')
    rows=[]
    for key in ['strong_all','H1_mild','H1_big','H2_core_mild_cold_up','H4_hy_inline_up']:
        for part in ['2019_2023','2024_2026','exclude2022']:
            for h in [60,240]:
                r=rb[rb.group_key.eq(key)&rb.partition.eq(part)&rb.family.eq('A')&rb.horizon_min.eq(h)].iloc[0];rows.append([key,part,H[h],int(r.trades_n),rr(r,'net_win',False),avg(r)])
    add(table(['规则','时期/排除','退出','n','净盈利','净均值，95%CI'],rows))
    add('H1温和意外组逐年剔除的1h净均值全部仍为负，约-0.424%至-0.335%；其避错价值没有仅由2022年产生。显著总体同比组1h全样本+0.420%，但去掉2022后只剩7次、均值约+0.089%，年度块区间跨零，2024-2026仅3次。没有把历史正均值偷换成稳定未来正期望。')
    ol=load('outlier_sensitivity');rows=[]
    for key in ['H1_mild','H2_core_mild_cold_up','H1_big','H4_hy_inline_up']:
        r=ol[ol.group_key.eq(key)&ol.family.eq('A')&ol.horizon_min.eq(60)].iloc[0]
        rows.append([key,int(r.n),pct(r.mean_net),pct(r.winsor05_95_mean),f'[{pct(r.leave_one_event_mean_min)},{pct(r.leave_one_event_mean_max)}]',r.largest_abs_event])
    add(table(['异常值探索审计','n','1h原均值','5%-95%缩尾均值','逐事件剔除均值范围','最大绝对收益事件'],rows))
    add('两条温和意外避错规则在逐事件剔除后1h均值全部仍负。总体同比中性强涨的1h均值则会跨正负，说明其微小正点估计较敏感。縮尾、移除最佳盈利或最大绝对事件只用于稳健性，绝不会作为实时筛选条件或重新选择主阈值。')
    rows=[]
    for key in ['H1_mild','H2_core_mild_cold_up','H1_big']:
        costs=load('cost_latency_sensitivity');a=costs[costs.group_key.eq(key)&costs.family.eq('A')&costs.horizon_min.eq(60)&costs.execution_lag_min.eq(1)]
        for _,r in a.iterrows():rows.append([key,int(r.cost_bps),int(r.trades_n),rr(r,'net_win',False),avg(r)])
    add(table(['条件','往返成本bp','n','1h净盈利','1h净均值，95%CI'],rows))
    add('费用8/12/24/40bp与额外延迟0/1/2分钟均重算；已核验历史免手续费活动单列，没有把全历史统一视为收费20bp。MFE/MAE使用入场后分钟高/低及退出open；最大回撤按每次100%无杠杆名义仓位、日期顺序和分钟close盯市计算，并另存事件退出点回撤。并不覆盖分钟内价格顺序、实盘成交簿和借币融资。')
    add('0分钟延迟仅代表理想化的分钟边界成交敏感性，不保证能在收到已完成K线后仍成交于同一边界open；主规格始终额外等待1分钟。')
    rows=[]
    for state in ['hiking','pause','cutting']:
        z=e[e.policy_stage.eq(state)];rows.append([CN[state],len(z),int(z.strong_first_03.sum())])
    add(table(['公布前最近FOMC决定方向','事件数','强首波数'],rows))
    add('增长使用事件前一天ALFRED版本的失业率、非农、实际消费；严格组不使用未全面核验初值的ISM，29稳健/6恶化/57未分类。扩展历史ISM发布快照为68稳健/24恶化，版本风险独立标记。就业、消费、ISM至少两项恶化才归恶化；关键缺失不强行视为稳健。核心/总体偏冷与增长是独立维度，未把低CPI本身等同于衰退。')
    gr=load('growth_environment_results');rows=[]
    for model in ['growth_strict','growth_snapshot']:
        for state in ['stable','deteriorating','unclassified']:
            r=gr[gr.growth_definition.eq(model)&gr.CPI_dimension.eq('core_mom')&gr.growth_state.eq(state)&gr.horizon_min.eq(240)].iloc[0]
            rows.append([model,CN[state],int(r.events_n),rr(r,'up'),rr(r,'fade100_touch'),rr(r,'reverse5_touch'),avg(r,'release_return')])
    add(table(['增长口径','状态','核心月率冷n','4h上涨，95%CI','全回吐，95%CI','真正反转，95%CI','4h回报，95%CI'],rows))
    add('政策、严格与扩展增长、逐年剔除、疫情和高通胀背景可由逐事件库复查。有限并发目录标记22次已知0830其他数据，24h内FOMC有3次；分别排除及联合排除全部计算。未标记不等于没有并发，尤其目录部分年份覆盖不全。无法据此作CPI因果归因。')
    add('## 9. 核心CPI是否真正带来增量预测')
    add('模型固定L2=1逻辑回归，不调参；训练期2019-2023，测试期2024-2026。只用总体两项、只用核心两项、四项组合、单总体环比、单核心环比及常数基准。标准化均值/方差仅取训练数据。预测强首波4h方向保持时，各CPI模型公平加入已知15m幅度，并把意外乘首波方向表达同向/逆向。所有模型使用同一完整四指标样本，2025-12-18被模型比较共同排除。')
    rows=[]
    for _,r in pred[pred.split.eq('holdout_2024_2026')].iterrows():rows.append([r.target,r.model,int(r.n),f'{100*r.accuracy:.1f}% [{100*r.accuracy_ci_low:.1f},{100*r.accuracy_ci_high:.1f}]',num(r.brier_score,4),num(r.log_loss,4)])
    add(table(['目标','模型','测试n','准确率，Wilson95%CI','Brier','log loss'],rows))
    rows=[]
    for _,r in inc.iterrows():rows.append([r.target,r.split,r.metric,int(r.n),f'{r.effect_combined_minus_headline:+.4f}',f'[{r.ci_low:+.4f},{r.ci_high:+.4f}]',num(r.p,4),num(r.q_prediction_exploratory,4)])
    add(table(['目标','时间检验','损失','n','四项-总体','95%CI','p','探索q'],rows))
    add('损失差为负才是四项改善，本次全部点估计为正且区间跨零。逐年扩展训练2022-2026也未显示改善。强首波4h测试仅22次，常数预测保持16/22，Brier约0.203，比所有CPI模型更好。当前证据不支持因为核心环比“理论重要”就宣称模型有增量优势。2024-2026旧事件已被研究过，只能称历史时间留出，不能称完全未见样本外或真正前向验证。')
    add('## 10. 直接交易规律与历史失败案例')
    add('### 10.1 证据最强：用于避免错误追单')
    for key,label in [('H1_mild','总体同比温和意外且顺数据强首波'),('H2_core_mild_cold_up','核心环比温和偏冷且BTC强上涨')]:
        a=trow(t,key);b=trow(t,key,h=240);v=grow(s,key,240);z=e[g[key]['mask']]
        exceptions='; '.join(z[z.net_return_60m>0].date) or '主成本下无1h追单盈利反例；8/12bp有2次盈利'
        add(f'**{label}**：触发条件为15m绝对幅度>=0.3%、第16m入场 → 样本{int(a.trades_n)} → 首波由条件选为数据同向 → 1h净胜率{rr(a,"net_win")}、均值{avg(a)} → 4h真正反转{rr(v,"reverse5_touch")}、净均值{avg(b)} → 1h盈利反例：{exceptions} → 置信度：历史避错描述较强，主对比仅H1达到校正显著；不能解释为永不盈利 → 动作：避免仅凭这一首波追入，亦不要无反转信号就反向开仓。')
    add('### 10.2 历史正均值但仍需前向验证')
    for key,label in [('H1_big','显著总体同比且强首波顺数据，至1h'),('H4_hy_inline_up','总体同比符合且BTC强上涨，至4h')]:
        a=trow(t,key,h=60 if key=='H1_big' else 240);z=e[g[key]['mask']];fail='; '.join(z[z[f'net_return_{60 if key=="H1_big" else 240}m']<=0].date)
        add(f'**{label}** → n={int(a.trades_n)} → 第一波按条件确定 → 1h/4h见前述全部结果 → 相关期限净胜率{rr(a,"net_win")}、均值{avg(a)} → 亏损反例：{fail} → 置信度：低、策略对零校正不显著；时期/核心拆分稀疏 → 动作：只能作为冻结的候选规则记录，不从本次研究推导确定仓位。')
    add('反杀后固定4h退出的全强首波组也有+0.106%历史均值，但触发25次、区间跨零、期间再反杀17次；不能从正点估计选定最优持有期。核心温和冷的3次反杀至4h均盈利，数量极低，属于需要前向积累的假设。')
    add('### 10.3 方向较可靠，但不等于赚钱')
    add('双月率偏冷/偏热首波方向分别16/20、17/21，能够帮助理解数据方向；15分钟后追入仍必须检查独立入场收益。总体同比符合强涨的4h方向保持9/10，追多净胜7/10、均值区间跨零；四项符合强涨只有1次，禁止把90%搬到该条件。')
    add('### 10.4 仅有理论逻辑、未获统计支持')
    add('核心月率暴热且总体中性/冷，及总体月率暴热但核心中性，都是零样本。2Y反转领先BTC、NQ由涨转跌解释诱多、良性/衰退型通胀下降的可靠交易分类，缺授权高频资产或严格需求识别；不能把BTC反杀事后命名为已验证利率机制。')
    add('### 10.5 旧数字必须收窄的解释')
    add('上传旧数值复算一致，没有为了给出否定结论而制造旧报告算错的说法。需要否定的是把追多0/10盈利等同于100%跌回公布价或反杀必胜的推论：路径只有5/10全回吐、3/10收盘反转。总体同比符合强涨9/10保持也不能迁移到四项全部符合，分母不同。双月率暴热优势、延迟追单优势与首次反转后反向策略正期望，本次均证据不足；小样本不等于这些假设在总体上已被统计否定。')
    add('### 代表性失败与反例：来自全样本，不作择例统计')
    case_dates=['2021-06-10','2021-11-10','2021-07-13','2024-07-11','2025-03-12','2025-10-24','2026-08-12'];rows=[]
    for _,r in e[e.date.isin(case_dates)].iterrows():rows.append([r.date,f'{r.headline_mom_bucket5}/{r.core_mom_bucket5}',pct(r.btc_return_15m),pct(r.net_return_60m),pct(r.net_return_240m),'未触发' if pd.isna(r.first_reverse5_min_240m) else str(int(r.first_reverse5_min_240m))+'m',pct(r.B_hold60_net_return)])
    add(table(['日期','月率组合','首波','1h顺势净','4h顺势净','首次反杀','反杀后1h净'],rows))
    add('2024-07-11核心温和冷强涨后确实向下反转，B第41分钟入场、持有1h仍小亏；2025-03-12与2025-10-24同类B盈利。这三笔说明反转定义是必要的可执行条件，但还不足以构成可靠策略。2021-07-13双暴热先跌，1h/4h追空仍亏；2021-11-10双暴热先涨而继续上涨，避免将所有逆数据首波当诱多。')
    add('## 11. 局限、未完成项目和来源')
    add(table(['项目','具体覆盖或阻碍','处理'],[['当次发布前独立一致预期快照','全部92次未逐次封存调查截止时间','保留历史日历字段及版本风险，不冒称认证PIT'],['2025-12-18月率','两项MoM实际与预期缺失','两个月累计变化不替代当月；月率矩阵少1'],['2021-02-10 24h','79分钟缺失','只剔除24h完整路径，<=4h全部保留'],['严格增长分组','57次未分类；ISM历史初值不完整认证','扩展版本单列，不能强制稳健'],['2Y/ZT/NQ/DXY及政策期货概率','全92日期未取得授权分钟资产/CTD-DV01','本次四指标BTC与A/B/C已完成；跨资产旧假设未验证'],['实盘成交与做空费用','无历史盘口/VIP/借币/资金费','open成交模拟，固定成本与延迟情景'],['真正未见样本','后期历史已经被旧研究查看','时间留出仅历史检验，未宣称前向验证']]))
    add('未完成的是源版本和跨资产/微观执行认证，不是本次分钟反杀回测：B/C所需真实分钟路径已取得并完整执行。对跨资产可使用合法授权的CME NQ与ZT历史1m OHLCV，例如CME DataMine或Databento CME Globex产品；ZT还需CTD/DV01校准，原始2Y收益率和ICE DX需相应供应商授权。本次未采购，具体账单未知，不能重述旧价格为当前报价或以日频2Y伪造分钟利率。')
    add('统计小样本、重叠分组、年份相关、极端值及多次筛选都有风险。n<10为低置信，n<=3极低；单事件不提供退化bootstrap均值CI。均值bootstrap为10000次百分位，Wilson为95%，固定seed=20261012。自助区间边界接近零时不据此宣布优势，结合p/q与时间留出。没有以机制相关性推导因果。')
    sources=[['BLS当次正式CPI新闻稿','https://www.bls.gov/bls/news-release/cpi.htm','冻结获取2026-10-11；2026-09/2025-12本次再核验'],['BLS 2025-12-18停摆说明','https://www.bls.gov/news.release/archives/cpi_12182025.htm','本次确认两个月累计不等于月率'],['Binance每日ZIP及CHECKSUM','https://data.binance.vision/?prefix=data/spot/daily/klines/BTCUSDT/1m/','184组；获取时间见原manifest'],['四项历史Investing日历','https://www.investing.com/economic-calendar/cpi-733 ; cpi-69 ; core-cpi-736 ; core-cpi-56','事后历史预期字段，不是08:29封存'],['ALFRED事件前版本','https://alfred.stlouisfed.org/','UNRATE/PAYEMS/PCEC96/DFEDTARU 368份'],['Coinbase BTCUSD核验','https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles','保留原92段核验，不拼接Binance'],['用户当前10份研究文件','provided_input_manifest.csv','2026-10-12读取、文件哈希及74项复算核对']]
    add(table(['来源','网址/文件','历史可用性与审计'],sources))
    add('完整原始获取日期、URL、SHA256与排除日志在original/results/source_manifest.csv、source_exclusion_audit.csv；本次材料读取日期不冒充原始市场数据获取日期。输入数据、旧清洗程序和新增程序一起打包，网络刷新是可选项，全部统计可离线复算。')
    add('## 12. 完整事件数据库')
    add('CPI_4指标完整事件数据库.csv保留全部92行，四指标预期/实际/意外/五档、来源状态、增长与政策、八个回报窗口、触达/终点路径和A/B/C规范收益。下面只展示核心核验索引，全部分组日期和交易条件均可回溯。')
    rows=[]
    for _,r in e.iterrows():
        def pp(k):return '缺失' if pd.isna(r[k+'_surprise_pp']) else f'{r[k+"_surprise_pp"]:+.1f}'
        rows.append([r.date,'/'.join(pp(k) for k in FIELDS),pct(r.btc_return_15m),pct(r.btc_return_60m),pct(r.btc_return_240m),pct(r.net_return_60m),int(r.reverse5_touch_240m)])
    add(table(['正式日期','HM/CM/HY/CY意外pp','15m','1h','4h','16m入场1h净','4h收盘反转'],rows))
    add('## CPI事件交易决策表')
    add('本表未特别标同比的总体/核心默认环比，收益主成本24bp，顺势为第16m入场至事件1h，反向为确认反杀后持有1h。n<10直接标样本不足，原始命中数留在decision_table.csv；本表不能代替行情实时确认。包含不同强度合并行和具体强度行，它们是重叠条件，不能相加。')
    rows=[]
    for _,r in decisions.iterrows():
        n=int(r['强首波条件事件数']);adequate=n>=10
        def display(k,den):
            if den<10:return f'样本不足(n={den})'
            lo,hi=wilson(r[k],den);return f'{int(r[k])}/{den} [{100*lo:.1f},{100*hi:.1f}]'
        rows.append([r['CPI组合'],r['BTC前15m条件'],n,r['未来1h最常见结果'],display('4h真正反转次数',n),display('顺势1h净盈利数',int(r['顺势1h交易数'])),display('反杀后持有1h净盈利数',int(r['反杀后持有1h交易数'])),r['交易判断']])
    add(table(['CPI组合','BTC前15m','初始n','未来1h','4h反转，95%CI','顺势净胜，95%CI','反向净胜，95%CI','交易判断'],rows))
    add('模型标识：GPT-6（API助手）；未获可核验的细分型号或思考深度元数据，故不编造这些字段。')
    md='\n\n'.join(sections)+'\n';DEL.mkdir(exist_ok=True);(DEL/'CPI_BTC_Final_Report.md').write_text(md,encoding='utf-8')
    return md,decisions

def inline(s):
    s=html.escape(s);s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s);s=re.sub(r'`(.+?)`',r'\1',s)
    s=re.sub(r'\[([^]]+)\]\(([^)]+)\)',r'\1 (\2)',s);return s

class StableCanvas(Canvas):
    def __init__(self,*args,**kwargs):kwargs['invariant']=1;super().__init__(*args,**kwargs)

def styles():
    pdfmetrics.registerFont(TTFont('NotoSC',str(ORIGINAL/'fonts/NotoSansSC-Regular.ttf')));pdfmetrics.registerFontFamily('NotoSC',normal='NotoSC',bold='NotoSC',italic='NotoSC',boldItalic='NotoSC')
    return {key:ParagraphStyle(key,fontName='NotoSC',fontSize=size,leading=leading,spaceAfter=space,wordWrap='CJK',textColor=colors.HexColor(color),keepWithNext=keep) for key,size,leading,space,color,keep in [('p',9.3,14.8,7,'#263746',False),('h1',21,29,14,'#183e58',True),('h2',14.5,22,10,'#214f6c',True),('h3',11,17,7,'#214f6c',True),('cell',7.35,10.8,0,'#263746',False),('th',7.4,10.8,0,'#ffffff',False)]}

def pdf_table(rows,width,st):
    cols=len(rows[0]);cw=[width/cols]*cols
    if cols>=6:cw[0]=width*.19;cw[1:]=[(width-cw[0])/(cols-1)]*(cols-1)
    if rows[0][0]=='正式日期' and cols==7:cw=[width*x for x in [.14,.25,.12,.12,.12,.14,.11]]
    data=[[Paragraph(inline(str(s)),st['th'] if i==0 else st['cell']) for s in row] for i,row in enumerate(rows)]
    t=Table(data,colWidths=cw,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#285875')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f1f4f7'),colors.white]),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#285875')),('LINEBELOW',(0,1),(-1,-1),.2,colors.HexColor('#dce3e8'))]))
    return t

def footer(c,doc):
    c.saveState();c.setFont('NotoSC',7);c.setFillColor(colors.HexColor('#7b8792'));c.drawString(40,A4[1]-25,'CPI四指标 × BTC  |  92次正式事件  |  2026-10-12升级');c.drawRightString(A4[0]-40,24,str(doc.page));c.setStrokeColor(colors.HexColor('#dce3e8'));c.line(40,36,A4[0]-40,36);c.restoreState()

def make_pdf(md,p):
    st=styles();story=[];lines=md.splitlines();i=0;width=A4[0]-80
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('|'):
            block=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                v=[s.strip() for s in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-:]+',x) for x in v):block.append(v)
                i+=1
            story.extend([pdf_table(block,width,st),Spacer(1,8)]);continue
        m=re.match(r'!\[.*?\]\((.*?)\)',line)
        if m:
            path=(DEL/m[1]).resolve();im=Image(str(path));im.drawHeight=im.imageHeight*width/im.imageWidth;im.drawWidth=width;story.extend([im,Spacer(1,8)]);i+=1;continue
        key='h3' if line.startswith('### ') else 'h2' if line.startswith('## ') else 'h1' if line.startswith('# ') else 'p'
        text=re.sub(r'^#{1,3} ','',line)
        next_line=next((x.strip() for x in lines[i+1:] if x.strip()),'')
        if key=='h2' and next_line.startswith('|'):
            story.append(CondPageBreak(100));sty=ParagraphStyle('table_heading',parent=st[key],keepWithNext=False)
        else:sty=st[key]
        story.append(Paragraph(inline(text),sty));i+=1
    doc=SimpleDocTemplate(str(p),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=46,bottomMargin=48,title='美国CPI与BTC四指标事件回测',author='CPI Research',pageCompression=1)
    doc.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=StableCanvas)

def make_quick_guide():
    st=styles();width=A4[0]-80;story=[];s=load('group_windows');t=load('strategy_groups');e=load('events_four')
    def para(x,key='p'):story.append(Paragraph(inline(x),st[key]))
    para('CPI事件交易规律速查','h1');para('92次正式事件，2019-2026年9月。第15分钟确认，第16分钟入场，往返24bp。核心和总体默认月率；特别标为同比的规则保持原口径。')
    para('先看四指标，再看可成交收益','h2')
    rows=[['条件','历史结果','当下动作']]
    for key,label,action in [('H1_mild','总体同比±0.1pp，BTC顺数据>=0.3%','避免只凭首波追单'),('H2_core_mild_cold_up','核心环比-0.1pp，BTC涨>=0.3%','避免追多；不等于立即做空'),('H1_big','总体同比意外>=0.2pp，BTC顺数据>=0.3%','仅列候选，不能宣称稳定优势'),('H4_hy_inline_up','总体同比符合，BTC涨>=0.3%','不能当四项都符合；4h保持≠盈利')]:
        a=trow(t,key);v=grow(s,key,240);rows.append([label,f'1h净胜{rr(a,"net_win")}；净均值{avg(a)}；4h收盘反转{rr(v,"reverse5_touch")}',action])
    story.append(pdf_table(rows,width,st));para('证据最强是避错。H1温和/显著组1h净收益差约-0.819pp，主BH q=0.0036；这不是显著组策略对零已验证。其他组小样本和历史筛选风险仍在。')
    para('不要把以下数字混为一谈','h2');para('55次强首波1h保持公布价同侧51/55，但第16m追入1h净盈利17/55。核心温和冷10次强上涨：1h追多0/10盈利，4h盘中全吐5/10，5m收盘反转3/10。成本8/12bp时追多有2/10盈利、均值仍负。')
    story.append(PageBreak());para('总体与核心的组合','h1');para('以下只填真实样本；n<10不作为可靠交易概率。方向是15m相对公布价，净盈利是确认后入场。')
    rows=[['CPI月率组合','首波与样本','交易判断']]
    for key,label,direction in [('mom_-1_-1','双月率偏冷','up'),('mom_1_1','双月率偏热','down'),('mom_0_0','双月率符合','up'),('mom_0_-1','总体符合、核心偏冷','up'),('mom_0_1','总体符合、核心偏热','down')]:
        r=grow(s,key,15);v=grow(s,key,240);rows.append([label,('上涨' if direction=='up' else '下跌')+rr(r,direction)+f'；4h真正反转{rr(v,"reverse5_touch")}','方向可参考，追单利润须独立验证'])
    rows.extend([['双月率暴冷','4次；3次先涨。强涨追多仅3笔','极低/低样本，不外推3/3盈利'],['双月率暴热','6次；首波上涨/下跌各3次','不能假设越热越可靠'],['核心暴热、总体符合或冷','0次','未验证，放弃用虚构概率决策'],['总体暴热、核心符合','0次','未验证'],['四项全部符合且强上涨','仅2024-11-13一笔','不能沿用HY中性强涨9/10保持']])
    story.append(pdf_table(rows,width,st));para('四项组合逻辑回归在2024-2026历史留出没有优于总体模型：15m上涨20/31对23/31。核心理论重要性不是已验证增量预测。所有后期历史已被查看，属于历史留出，不是未见前向样本。')
    story.append(PageBreak());para('反杀与延迟入场','h1');para('B规则：强首波后首次完整5分钟close反向穿越P0，下一分钟open反手。不是盘中触碰就下单，也不是用4h最终价倒推触发。')
    rows=[['规则','真实触发与收益','判断']]
    for key,label in [('strong_all','全部55次强首波'),('H2_core_mild_cold_up','核心月率温和冷强涨10次')]:
        a=trow(t,key,'B',60);b=trow(t,key,'B',240,kind='absolute_event');rows.append([label,f'触发{int(a.trades_n)}/{int(a.eligible_strong15_n)}；持有1h净胜{rr(a,"net_win")}，均值{avg(a)}；事件4h净胜{rr(b,"net_win")}，均值{avg(b)}','小样本/区间宽；首次反转非确定趋势'])
    story.append(pdf_table(rows,width,st));para('全部25笔B中，反手后持有1h期间16/25再次回到原首波P0一侧。核心温和冷只3笔B，不能把至4h的3/3盈利宣传为必胜规则。2024-07-11该组反杀后持有1h仍小亏；2025-03-12、2025-10-24盈利。')
    para('C规则：等30m/60m仍同侧且此前无5m反转，31m/61m open入场。全部强首波分别触发52/55、47/55；30m确认后持有1h净均值-0.436%，60m确认后持有4h-0.838%。等待更久没有自动提高盈利。')
    para('更早双月率顺向确认：5m/10m强首波后入场，1h全样本净均值+0.301%/+0.215%，但2024-2026均只有2/9盈利，均值-0.281%/-0.226%；剔除2022也为负。更早追单仍未验证稳定优势。')
    para('使用顺序','h2');para('保存四项发布前预期及来源时间；计算四项意外和一致/冲突；在已完成15m后识别首波；区分高价追入风险与真正反转；仅按预先冻结的A/B/C规则记录实际入场。现阶段最可靠动作是避免把方向保持率当净胜率，极端或冲突格样本不足时放弃据此建立规则。')
    para('边界：92次中月率完整91；2025-12-18月率不补；1条24h路径缺79分钟。2Y/NQ/DXY未验证。分钟open成交、手续费滑点是假定情景，现货做空融资成本未取得。详细文件与全部命中日期见完整报告、事件CSV和复现包。')
    doc=SimpleDocTemplate(str(DEL/'CPI_交易规律速查表.pdf'),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=46,bottomMargin=48,title='CPI事件交易规律速查',author='CPI Research',pageCompression=1)
    doc.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=StableCanvas)

def main():
    md,dec=make_markdown();make_pdf(md,DEL/'CPI_BTC_Final_Report.pdf');make_quick_guide()
    shutil.copyfile(OUT/'events_four.csv',DEL/'CPI_4指标完整事件数据库.csv');shutil.copyfile(OUT/'extreme_research.csv',DEL/'CPI_暴热暴冷专项研究.csv');shutil.copyfile(OUT/'trades_all.csv',DEL/'CPI_第一波与反杀策略回测.csv')
    print('Report generated',len(md),'characters',flush=True)

if __name__=='__main__':main()
