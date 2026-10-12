"""Generate Chinese report and exact static charts from audited CSVs, then PDF."""
from net import ROOT
from summarize import wilson,boot_ci
import pandas as pd,numpy as np,re,html,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.pdfgen import canvas
os.environ['SOURCE_DATE_EPOCH']='1791676800'  # 2026-10-11 00:00 UTC: reproducible report metadata

def load(name):return pd.read_csv(ROOT/'results'/f'{name}.csv')
def pct(v,d=2):return '未验证' if pd.isna(v) else f'{v*100:+.{d}f}%'
def rate(r,k):return f"{int(r[k+'_count'])}/{int(r[k+'_n'])}={r[k+'_rate']*100:.1f}% [{r[k+'_ci_low']*100:.1f},{r[k+'_ci_high']*100:.1f}]"
def avg(r,k='net_return'):return f"{pct(r[k+'_mean'])} [{pct(r[k+'_mean_ci_low'])},{pct(r[k+'_mean_ci_high'])}]"
def direct_rate(k,n):
 lo,hi=wilson(k,n);return f'{k}/{n}={100*k/n:.1f}% [{100*lo:.1f},{100*hi:.1f}]' if n else '未验证'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in rows])
CN={'hot':'高于预期','cold':'低于预期','inline':'符合预期','stable':'增长稳健','deteriorating':'增长恶化','unclassified':'未分类','hiking':'末次加息','cutting':'末次降息','pause':'末次不变','mild':'温和','large':'显著','missing':'缺失'}
H={30:'30分钟',60:'1小时',240:'4小时',1440:'24小时'}

def charts(f,x):
 font=FontProperties(fname=str(ROOT/'fonts/NotoSansSC-Regular.ttf'))
 plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10,'axes.unicode_minus':False})
 g=f[(f.strategy=='momentum')&(f.exit_rule=='fixed')&(f.split=='all')&(f.roundtrip_cost_bps==24)].sort_values('horizon_min')
 fig,ax=plt.subplots(figsize=(9.2,4.2));pos=np.arange(4)
 for key,off,color,label in [('keep',-.16,'#157e8a','相对公布价方向保持'),('net_win',.16,'#db773e','确认后入场净盈利（24bp成本）')]:
  y=g[key+'_rate'].to_numpy()*100;err=np.vstack([y-g[key+'_ci_low'].to_numpy()*100,g[key+'_ci_high'].to_numpy()*100-y]);ax.bar(pos+off,y,.30,color=color,label=label,yerr=err,capsize=3)
  for a,b,r in zip(pos+off,y,g.to_dict('records')):ax.text(a,b+4,f"{int(r[key+'_count'])}/{int(r[key+'_n'])}",ha='center',fontsize=9)
 ax.set_xticks(pos,[H[h] for h in g.horizon_min],fontproperties=font);ax.set_ylim(0,118);ax.set_ylabel('概率（%）；误差线为Wilson 95%区间',fontproperties=font);ax.legend(prop=font,loc='lower left');ax.set_title('第一波方向保持 ≠ 确认后追单盈利',fontproperties=font,fontsize=15);fig.tight_layout();fig.savefig(ROOT/'figures/holding_vs_trading.png',dpi=180);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(9.2,4.2))
 for ax,h in zip(axs,[30,240]):
  for cl,col in [('cold','#157e8a'),('hot','#b85049'),('inline','#87959d')]:
   g=x[(x.horizon_min==h)&(x.headline_yoy_class==cl)];ax.scatter(np.full(len(g),{'cold':0,'hot':1,'inline':2}[cl])+np.linspace(-.15,.15,len(g)),g.release_return*100,s=17,alpha=.7,color=col)
   ax.scatter({'cold':0,'hot':1,'inline':2}[cl],g.release_return.mean()*100,marker='_',s=450,color='black',linewidths=2)
  ax.axhline(0,color='#bbb',lw=1);ax.set_xticks([0,1,2],['低于预期','高于预期','符合预期'],fontproperties=font);ax.set_title(H[h]+'相对公布基准收益',fontproperties=font);ax.set_ylabel('BTC回报（%）；黑线为均值',fontproperties=font)
 fig.suptitle('全部正式事件：方向分布与异常值同时保留',fontproperties=font,fontsize=14);fig.tight_layout();fig.savefig(ROOT/'figures/cpi_return_distribution.png',dpi=180);plt.close(fig)

def make_markdown():
 f=load('table_F_strategies');a=load('table_A_headline');first=load('first_wave');p=load('event_paths');x=p[(p.confirm_min==15)&(p.status=='ok')];ev=load('table_G_events');tests=load('hypothesis_tests');charts(f,x)
 main=f[(f.strategy=='momentum')&(f.exit_rule=='fixed')&(f.split=='all')&(f.roundtrip_cost_bps==24)].sort_values('horizon_min')
 sections=[]
 def add(s):sections.append(s.strip())
 add('# 美国CPI公布后BTC：第一波与二次定价历史回测\n\n2019-01-11—2026-09-11｜研究截止2026-10-11｜92次正式发布\n\n完整CPI与BTC主研究；增长严格PIT与扩展快照分开；H2/H4未取得联合高频样本。所有结果由冻结公开数据及附带Python代码计算。')
 add('## 1. 执行摘要：已验证结论与交易价值')
 add('**最重要的发现是：第一波在公布价同侧保持，与确认后入场盈利存在很大差距。** 在15分钟绝对变动≥0.3%的55次事件中，30分钟仍保持第一波方向52/55；但等待确认后一分钟入场，扣除24bp往返成本，盈利只有15/55。不能把前者94.5%称为交易胜率。')
 add(table(['退出时点','样本n','方向保持率，95%CI','确认后净胜率，95%CI','平均净收益，95%CI'],[[H[r.horizon_min],r.n,rate(r,'keep'),rate(r,'net_win'),avg(r)] for _,r in main.iterrows()]))
 add('主成本是VIP0参考费率20bp加假定滑点4bp的线性本金情景；不是历史逐笔真实成交成本。对已核实的2022-07-08至2023-03-22 BTCUSDT零手续费活动单独调整，30分钟平均净收益变为−0.095%、4小时−0.482%，仍未显示稳定正优势。现货做多结果单列；做空缺借贷成本，属于条件模拟。')
 add('Headline YoY低于预期时第一波上涨22/32=68.8%；高于预期时第一波下跌22/36=61.1%；符合预期时第一波上涨16/24=66.7%。冷与热CPI的公布后30分钟、1小时回报分布有可检测差异，但这不是15分钟追入的获利证明。H1与H3主比较经多重校正均未显著：增长稳健不保证冷CPI上涨延续，热CPI下跌也没有被验证为可靠更强的4小时延续。')
 add('H2、H4、跨资产确认策略和利率逆转退出**未验证**。缺的是92个日期的2Y/ZT/NQ实际分钟路径、ZT久期校准及历史政策期货快照，不是用日频收益率即可补齐的问题。BTC、四项CPI及可取得增长数据的完整回测已经完成；本报告不会把未验证的利率推断混入已测结果。')
 add('## 2. 历史事实：不同CPI结果与宏观环境')
 add('### 正式事件分母与旧PDF复核')
 add(table(['年份','BLS实际发布次数','处理'],[[y,n,'全年' if y<2025 else '10月参考月未公布；9月数据延至10-24' if y==2025 else '截至09-11，下一次10-14尚未公布'] for y,n in ev.groupby('year').size().items()]))
 add('合计92次，而不是机械月度槽位93次。2025年10月参考月没有CPI新闻稿；2025-10-24是9月数据的实际发布日。2025-12-18的11月数据有YoY，但缺10月基数，所以Headline/Core MoM实际值及预期均缺失；仅排除月率分类，不排除该次BTC或同比结果。2019年1–7月7次的统一历史预期字段现已取得，旧第一份PDF的85次有效分母扩展为92次。')
 legacy=load('legacy_audit');ll=legacy[legacy.recomputed_eligible];rows=[]
 for h in [30,60,240]:rows.append([H[h],direct_rate(int(ll[f'legacy_keep_{h}m'].sum()),len(ll)),direct_rate(int((ll[f'net_return_entry11_{h}m']>0).sum()),len(ll))])
 add(table(['旧14次规格','独立重算公布价同侧保持','10分钟确认后11分钟入场净盈利（24bp）'],rows))
 lg=load('legacy_strategy_statistics');rows=[]
 for _,r in lg.iterrows():rows.append([{'all':'旧规则全样本','explore_2019_2023':'2019–2023','holdout_2024_2026':'2024–2026'}[r.split],H[r.horizon_min],r.n,avg(r),f'{r.q_value:.3f}'])
 add(table(['旧规则实际交易','时点','n','净均值，95%CI','BH q'],rows))
 add('旧14次规则的30分钟与1小时净均值确实略正（约+0.153%/+0.181%），不应因胜率低而说所有收益都负；其区间跨零、校正不显著，而且2024–2026的6次30分钟仅1次净盈利、平均−0.366%。这项小样本规则尚不能宣布具有稳定样本外优势。')
 add('旧14次选择条件为10分钟波动≥0.5%、两段5分钟同向且与Headline YoY意外方向相符，目标保持须同侧≥0.25%。92次逐一筛选后，入选日期与旧表完全相同，无额外漏入/漏出。旧14/14、12/14、8/14属于这种筛选后的方向结果，不能证明100%交易胜率；其中“利率信号一致”只是CPI方向推断，未独立取得真实利率分钟路径。旧14个事件完整重算见legacy_audit.csv。')
 add('### 表A：CPI分类、第一波与公布后回报')
 rows=[]
 for cl in ['hot','cold','inline']:
  r=first[(first.confirm_min==15)&(first.group_field=='headline_yoy_class')&(first['group']==cl)].iloc[0];ar=a[(a.first_wave_filter=='all')&(a.headline_yoy_class==cl)]
  rows.append([CN[cl],int(r.n),direct_rate(int(r.up_count),int(r.n)),avg(ar[ar.horizon_min==30].iloc[0],'first_return'),int(r.up_ge03_count),int(r.down_ge03_count)])
 add(table(['Headline YoY','n','15分钟上涨率，95%CI','15分钟均值，95%CI','≥0.3%上涨次数','≤−0.3%下跌次数'],rows))
 rows=[]
 for cl in ['hot','cold','inline']:
  for _,r in a[(a.first_wave_filter=='all')&(a.headline_yoy_class==cl)].sort_values('horizon_min').iterrows():rows.append([CN[cl],H[r.horizon_min],r.n,avg(r,'release_return'),pct(r.release_return_median)])
 add(table(['CPI结果','时点','n','相对公布价平均回报，95%CI','中位数回报'],rows))
 add('此表包含全部事件，不要求第一波达到门槛；正负是BTC绝对方向，非交易方向收益。平均数受极端事件影响，原始分布和中位数均保留。Headline同比符合预期仍可能Core或月率意外，不能把“符合”当作没有信息。')
 add('![CPI回报分布](figures/cpi_return_distribution.png)')
 at=load('table_A_tests');r=at[(at.comparison=='A_cold_minus_hot_30m')].iloc[0];r1=at[(at.comparison=='A_cold_minus_hot_60m')].iloc[0]
 add(f'探索性冷−热回报差：30分钟{pct(r.effect_a_minus_b)}，置换p={r.p_value:.4f}、BH q={r.q_value:.4f}；1小时{pct(r1.effect_a_minus_b)}，p={r1.p_value:.4f}、q={r1.q_value:.4f}。第一波上涨概率差+29.9个百分点，Fisher p=0.0167、q=0.0357。4小时冷−热均值差约+1.00%，q=0.0961，不能当作稳健显著。这里15项探索检验独立于主H1/H3家族校正。')
 add('### Headline/Core一致与冲突')
 rows=[]
 for period,label in [('yoy','同比'),('mom','月率')]:
  counts=ev['combo_'+period].value_counts();d=load('table_A_combinations_'+period)
  for combo,n in counts.items():
   cl1,cl2=combo.split('_');g=d[(d.first_wave_filter=='all')&(d['combo_'+period]==combo)&(d.horizon_min==240)]
   rows.append([label,CN[cl1]+' / '+CN[cl2],int(n),avg(g.iloc[0],'release_return') if len(g) else '未验证'])
 add(table(['口径','Headline / Core','n','4小时公布价回报均值，95%CI'],rows))
 add('同比真正方向冲突仅6次（热/冷4，冷/热2）；月率真正冲突仅1次，不能据此推导冲突场景的高置信交易规则。中性/偏热或中性/偏冷不是冲突。四项surprise、完整组合的方向/回吐/反转及核心单项结果见表A各CSV，避免把热与冷合并为一个延续率。')
 add('### 表C：意外幅度与非线性')
 c=load('table_C');rows=[]
 for cl in ['cold','hot']:
  for size in ['mild','large']:
   g=c[(c.first_wave_filter=='all')&(c.headline_yoy_class==cl)&(c.headline_yoy_size==size)]
   for _,r in g[g.horizon_min.isin([60,240])].iterrows():rows.append([CN[cl],CN[size],H[r.horizon_min],r.n,avg(r,'release_return')])
 add(table(['CPI方向','|意外|幅度','时点','n','公布价回报均值，95%CI'],rows))
 add('固定阈值：精确0为符合，0.1pp为温和，≥0.2pp为显著；这是公布到一位小数的数据，不宣称可识别更细意外。≥0.3pp另做敏感性，未改主规格。显著冷意外仅6次，平均上涨较强可能与疫情/FTX/政策时期重叠。不能把“意外更冷→上涨更强”的单变量相关关系直接写成增长恶化或可交易因果规则。增长×意外的探索HC3回归：严格PIT冷样本10次设计矩阵秩不足，交互无法识别；扩展32次的交互项q均≥0.25，未提供可靠非线性优势。全部回归及温和/显著置换差检验可复现。')
 ctests=tests[tests.comparison.str.startswith('C_')];rows=[]
 for _,r in ctests[ctests.comparison.str.endswith(('30m','60m','240m'))].iterrows():rows.append([CN['cold' if '_cold_' in r.comparison else 'hot'],r.comparison.rsplit('_',1)[-1],f'{r.n_a}/{r.n_b}',pct(r.effect_a_minus_b),f'[{pct(r.ci_low)},{pct(r.ci_high)}]',f'{r.p_value:.4f}/{r.q_value:.4f}'])
 add(table(['显著−温和意外','时点','组n','回报均值差','差值95%CI','置换p / 探索BH q'],rows))
 cq30=ctests[ctests.comparison=='C_cold_large_minus_mild_30m'].iloc[0];cq60=ctests[ctests.comparison=='C_cold_large_minus_mild_60m'].iloc[0]
 add(f'显著冷意外在30分钟与1小时比温和冷意外平均高约2.31和2.46个百分点，探索校正q分别{cq30.q_value:.4f}/{cq60.q_value:.4f}：样本内幅度关系得到支持。该信号在4小时校正后不显著，且显著组仅6次、增长交互未识别；不能外推为“越冷经济越差”或“越冷追涨净利润越强”。')
 add('## 3. H1—H4假设验证：概率、样本与反例')
 add('### H1：良性与需求恶化型通胀下降')
 add('增长状态在发布前固定，独立于CPI偏热/偏冷。UNRATE、PAYEMS、PCEC96及DFEDTARU全部取CPI前一天ALFRED vintage；367/368项通过可用性审计，2026-01-13实际PCE超过95天新鲜度门槛而缺失。就业恶化=失业率3个月上升≥0.2pp或非农3m均值低于6m均值；消费恶化=实际PCE水平3m变化≤0；ISM新订单恶化=3m均值低于50且低于前3m。至少两项恶化才归恶化。未知项用上下界，不把缺失当稳健。')
 add('严格组不使用未全面独立核验初值的ISM日历记录：92次分为稳健29、恶化6、未分类57。扩展组保留发布事件actual快照：稳健68、恶化24。它不是完全认证的PIT，不能替代严格组。增长恶化标签表示指标趋弱，不是NBER衰退判定，也不证明某次低CPI由需求恶化引起。')
 add('失业率趋势按准确日历月份取最新月与三个月前，不按四条非空记录计。2025年10月失业率缺失：2025-12-18、2026-01-13可用准确的8月/9月端点；2026-02-13需要10月端点而缺失，就业OR中的非农不恶化不足以确认整个就业模块不恶化，因此严格增长未分类。扩展组另有消费和ISM两个不恶化模块，可由上下界判稳健。该月份窗口审计完整保存，不跨缺口计算假三个月趋势。')
 rows=[]
 for spec in ['strict','snapshot']:
  b=load('table_B_'+spec);col='growth_'+spec
  for state in ['stable','deteriorating']+(['unclassified'] if spec=='strict' else []):
   gg=x[(x.horizon_min==30)&(x.headline_yoy_class=='cold')&(x[col]==state)];n=len(gg);rr=b[(b.first_wave_filter=='all')&(b[col]==state)]
   rows.append(['严格' if spec=='strict' else '扩展',CN[state],n,direct_rate(int((gg.first_return>0).sum()),n),avg(rr[rr.horizon_min==60].iloc[0],'release_return'),avg(rr[rr.horizon_min==240].iloc[0],'release_return')])
 add(table(['表B-1/冷CPI','增长状态','n','15分钟上涨率，95%CI','1小时回报，95%CI','4小时回报，95%CI'],rows))
 add('追涨机制必须进一步条件化于“第一波上涨≥0.3%”，不能把冷CPI却第一波下跌的事件混在同一诱多概率中。以下1h和4h概率以这种可识别上涨信号为分母。30分钟对应结果也完整保存于表B CSV。')
 rows=[]
 for spec in ['strict','snapshot']:
  bb=load('table_B_'+spec+'_up');col='growth_'+spec
  for state in ['stable','deteriorating']:
   for _,r in bb[(bb[col]==state)&bb.horizon_min.isin([60,240])].iterrows():rows.append(['严格' if spec=='strict' else '扩展',CN[state],H[r.horizon_min],r.n,rate(r,'keep'),rate(r,'fade50_touch'),rate(r,'fade100_touch'),rate(r,'reverse5_touch')])
 add(table(['表B-2','增长状态','时点','n','保持，95%CI','50%触达，95%CI','100%触达，95%CI','5m反转，95%CI'],rows))
 t=tests[(tests.comparison=='H1_strict_stable_minus_deteriorating_60m')&(tests.metric=='first_up')].iloc[0]
 st=int(((x.horizon_min==30)&(x.headline_yoy_class=='cold')&(x.growth_strict=='stable')&(x.first_return>0)).sum());bd=int(((x.horizon_min==30)&(x.headline_yoy_class=='cold')&(x.growth_strict=='deteriorating')&(x.first_return>0)).sum())
 add(f'严格冷CPI显著上涨组稳健仅3次、恶化仅2次，均低置信；4小时保持差（稳健−恶化）−16.7个百分点，95%CI [−65.5,+44.6]，Fisher p=1、BH q=1。扩展样本保持4/8对5/7，亦不支持稳健优于恶化。严格组未过滤首波门槛的上涨{st}/{int(t.n_a)}对{bd}/{int(t.n_b)}，差{100*t.effect_a_minus_b:+.1f}个百分点，95%CI [{100*t.ci_low:+.1f},{100*t.ci_high:+.1f}]，p={t.p_value:.3f}、q={t.q_value:.3f}。不能用这些少量样本确认或否定宏观机制，只能判为H1证据不足。')
 add('进一步检查：所有92次提取能源、住房、除能源服务YoY，91次提取对应MoM，同时保留四项CPI意外、实际消费及就业初值。冷CPI×Core MoM×能源月率分组见cold_components.csv。没有能源/住房/服务的独立调查预期和贡献权重归因，也没有充分需求因果识别，故未把任何事件武断标为“良性”或“需求衰退”。例如2023-04-12严格稳健且偏冷，显著上涨仍在4小时反转；2026-07-14同类却延续。')
 add('### H2：2Y下降下的宽松与增长恐慌')
 add(table(['表D：第一波联合状态','取得样本n','延续/诱多概率'],[['2Y↓ / NQ↑',0,'未验证'],['2Y↓ / NQ↓',0,'未验证'],['2Y↑ / NQ↓',0,'未验证'],['2Y↑ / NQ↑',0,'未验证'],['2Y持续↓ / NQ先↑后↓',0,'未验证']]))
 add('无真实联合路径，不能回答“2Y降而纳指跌时BTC上涨是否诱多”，也不能把当前观察的BTC反转归于增长恐慌。已检查可用接口与公开候选源，没有可合法核验的完整2Y/ZT/NQ数据输入。公共NQ候选GitHub项目只有代码和换月表，不等于所需报价。财政部日频2Y未进入任何15分钟统计。')
 add('### H3：高于与低于预期的方向不对称')
 hd=load('H3_aligned_details');rows=[]
 for cl in ['hot','cold']:
  for _,r in hd[(hd.cpi_class==cl)&hd.horizon_min.isin([60,240])].iterrows():rows.append([CN[cl]+'且首波'+('跌' if cl=='hot' else '涨'),H[r.horizon_min],r.n,rate(r,'keep'),rate(r,'fade100_touch'),rate(r,'reverse5_touch'),avg(r)])
 add(table(['条件（首波≥0.3%）','时点','n','保持，95%CI','100%回吐，95%CI','5m反转，95%CI','净收益均值，95%CI'],rows))
 add('4小时热下跌对冷上涨保持为11/15对9/15，差+13.3个百分点，95%CI [−19.0,+42.3]，Fisher p=0.700、q=1。热下跌100%回吐11/15、冷上涨7/15，差+26.7个百分点，95%CI [−7.7,+53.6]，p=0.264、q=1。热下跌并未被验证为更少回吐；样本中的反向结果也不足以宣称存在稳定相反规律。1小时热下跌净均值为正但CI跨零、q不显著，不能择优发布为策略。')
 ps=load('policy_stage');rows=[]
 for _,r in ps[ps.horizon_min==240].iterrows():rows.append([CN[r.policy_stage],CN[r.headline_yoy_class],r.n,rate(r,'keep'),avg(r)])
 add(table(['CPI前末次FOMC动作','CPI方向','有效首波n','4小时保持，95%CI','净均值，95%CI'],rows))
 add('该政策分层包含符合预期组，未把加息/降息/暂停期合并。多个格子n<10，降息期偏冷有效首波仅3次，不能当成衰退或降息必然利空BTC的证据。政策动作标签与市场下一次会议概率不同，后者尚缺；疫情、高通胀及快速加息标签全部在事件明细中，可作为后续制度稳健性检查。')
 add('### H4：利率信号逆转是否领先BTC')
 add(table(['表E：利率状态','取得样本n','BTC反转概率','对未逆转组差值','领先时间/退出收益'],[['维持',0,'未验证','未验证','未验证'],['逆转',0,'未验证','未验证','未验证'],['不明确',0,'未验证','未验证','未验证']]))
 add('没有利率路径，H4没有可估计概率、领先分钟数或真实利率退出收益。附带输入接口明确要求真实2Y分钟收益率或可审计校准；ZT价格不能直接等同2bp。规则为首波收益率变化≥2bp，随后对齐5分钟收盘穿越发布前基准且反向≥2bp。验证将用30/60分钟landmark，只用截至landmark已知的逆转信号、剔除BTC已反转事件，与未逆转组比较此后240分钟BTC反转，避免未来分组偏差。模块尚未在实测跨资产数据上验证。')
 add('## 4. 第一波与二次定价：延续、回吐及开盘')
 add('统一主规格：P0是08:30 ET前最后完整1m收盘；15分钟确认价取第15根收盘，第一波沿方向极值E取前15分钟最高/最低。主门槛0.3%。回吐均从确认以后开始计；终点指标独立。交易在确认闭合后再等待一分钟，以第16分钟open执行；不以P0入场。5m收盘反转需严格越过P0，50%回吐以E−P0而不是确认收盘幅度计。')
 add('![方向保持与交易盈利](figures/holding_vs_trading.png)')
 rows=[]
 for _,r in main.iterrows():rows.append([H[r.horizon_min],r.n,rate(r,'new_extreme_touch'),rate(r,'fade50_touch'),rate(r,'fade100_touch'),rate(r,'reverse5_touch')])
 add(table(['时点','n','创新极值触达，95%CI','50%回吐期间触达，95%CI','100%回吐期间触达，95%CI','5m反转期间触达，95%CI'],rows))
 rows=[]
 for _,r in main.iterrows():rows.append([H[r.horizon_min],r.n,rate(r,'fade50_end'),rate(r,'fade100_end'),rate(r,'reverse5_end')])
 add(table(['时点','n','终点≥50%回吐，95%CI','终点≥100%回吐，95%CI','终点5m反向，95%CI'],rows))
 add('方向保持与期间真正反转可同时发生：盘中越过P0后重新回到首波同侧，终点仍算保持。新极值与回吐亦可同时发生。目标时点恰好等于P0算100%回吐，不算严格反转。确认时已回吐50%也独立标记，避免混淆首波内部路径与确认后路径。')
 rows=[]
 for cl in ['hot','cold','inline']:
  for _,r in a[(a.first_wave_filter=='0.003')&(a.headline_yoy_class==cl)&a.horizon_min.isin([30,60,240])].iterrows():rows.append([CN[cl],H[r.horizon_min],r.n,rate(r,'keep'),rate(r,'reverse5_touch'),rate(r,'net_win'),avg(r)])
 add(table(['表A后续：首波≥0.3%','时点','n','方向保持，95%CI','期间反转，95%CI','净胜率，95%CI','净均值，95%CI'],rows))
 add('美国现金市场09:30 ET恰为事件后60分钟；60分钟方向保持51/55，240分钟37/55。配对有15次由保持变失效、1次由失效变保持，差−25.5个百分点，McNemar精确p=0.000519（探索）。但持有时长同时增加、跨资产未取得，不能把差值因果归于现金开盘。本研究记录这种时间位置，未声称识别了开盘冲击。')
 sens=load('sensitivity');rows=[]
 for _,r in sens[(sens.horizon_min==240)&sens['filter'].isin(['abs02','abs03','abs05','z1'])].iterrows():rows.append([int(r.confirm_min),r['filter'],r.n,rate(r,'keep'),rate(r,'net_win'),avg(r)])
 add(table(['确认分钟','门槛','n','4小时保持，95%CI','净胜率，95%CI','净均值，95%CI'],rows))
 add('abs02/03/05为0.2%/0.3%/0.5%；z1为首波绝对回报除以发布前60个分钟close产生的59个相邻1m log收益样本标准差×√确认分钟≥1，z2另存CSV。此波动率标准化假设短时扩散，不能充分处理事件跳跃。所有测试是敏感性，无最优参数选择；4小时均值在这些规格下均未显现正优势。')
 add('## 5. 交易执行：确认后的可交易收益')
 add('主模型把信号计算/下单延迟固定为一分钟，故15分钟确认、16分钟入场。最早第15分钟open属于零延迟的乐观分钟撮合近似，无法保证与闭合信号同一瞬间抢到；另测17分钟入场。三种延迟不重新选择信号或退出参数。')
 latency=load('execution_latency_sensitivity');rows=[]
 for _,r in latency[latency.horizon_min.isin([30,60,240])].iterrows():rows.append([int(r.entry_min_since_cpi),H[r.horizon_min],r.n,rate(r,'net_win'),avg(r)])
 add(table(['CPI后入场分钟','退出','n','净胜率，95%CI','净均值，95%CI'],rows))
 add('### 表F：固定菜单、成本与风险')
 rows=[]
 for name,label in [('momentum','BTC首波顺势'),('cpi_aligned','CPI方向与首波一致'),('long_momentum','只做现货多'),('short_momentum','理论空方向')]:
  for _,r in f[(f.strategy==name)&(f.exit_rule=='fixed')&(f.split=='all')&(f.roundtrip_cost_bps==24)&f.horizon_min.isin([30,60,240])].iterrows():rows.append([label,H[r.horizon_min],r.n,rate(r,'net_win'),avg(r),f'{r.profit_factor:.2f} / {r.payoff_ratio:.2f}',pct(r.minute_close_max_drawdown)])
 add(table(['策略','退出','n','净胜率，95%CI','净均值，95%CI','利润因子/盈亏比','分钟收盘最大回撤'],rows))
 add('利润因子=盈利总额/亏损总额绝对值；盈亏比=平均盈利/平均亏损绝对值；均为成本后统计。回撤按日期串行、每次100%无杠杆仓位的分钟收盘盯市并复利，手续费入/出各半近似扣减；表F另给事件退出点回撤，两者不可混称。原始分钟极值风险MFE/MAE与净中位数均保存。所有策略384个均值检验统一BH，未找到可宣布的显著正收益交易规则。')
 rows=[]
 for _,r in main.iterrows():rows.append([H[r.horizon_min],r.n,pct(r.mfe_mean),pct(r.mae_mean),pct(r.net_return_median),pct(r.close_to_close_max_drawdown)])
 add(table(['时点','n','平均MFE','平均MAE','净中位数','事件退出点最大回撤'],rows))
 rows=[]
 for split,label in [('explore_2019_2023','2019–2023探索'),('holdout_2024_2026','2024–2026时间留出')]:
  for _,r in f[(f.strategy=='momentum')&(f.exit_rule=='fixed')&(f.split==split)&(f.roundtrip_cost_bps==24)].iterrows():rows.append([label,H[r.horizon_min],r.n,rate(r,'net_win'),avg(r)])
 add(table(['时间分组','退出','n','净胜率，95%CI','净均值，95%CI'],rows))
 ho=f[(f.strategy=='momentum')&(f.exit_rule=='fixed')&(f.split=='holdout_2024_2026')&(f.roundtrip_cost_bps==24)&(f.horizon_min==30)].iloc[0];cl=load('year_cluster_bootstrap');cl=cl[cl.horizon_min==240].iloc[0]
 add(f'2024–2026的30分钟追单平均净收益及95%CI为{avg(ho)}，净盈利4/23。已知旧PDF部分后期案例，严格说这是时间留出检验，不能冒充完全未见样本外。逐年剔除后，主顺势四个期限均值全部仍负；4小时按8个年度块bootstrap区间[{pct(cl.ci_low)},{pct(cl.ci_high)}]，与事件bootstrap接近零的上界不同。年块只有8个，且多重策略检验不显著，避免夸大确定性。')
 rows=[]
 for cost in [8,12,24,40]:
  for _,r in f[(f.strategy=='momentum')&(f.exit_rule=='fixed')&(f.split=='all')&(f.roundtrip_cost_bps==cost)&f.horizon_min.isin([30,60,240])].iterrows():rows.append([cost,H[r.horizon_min],r.n,rate(r,'net_win'),avg(r)])
 add(table(['往返成本bp','退出','n','净胜率，95%CI','净均值，95%CI'],rows))
 fee=load('historical_fee_scenario');rows=[]
 for _,r in fee[(fee.strategy=='momentum')&(fee.split=='all')].iterrows():rows.append([H[r.horizon_min],r.n,r.zero_fee_events,rate(r,'net_win'),avg(r)])
 add(table(['历史手续费活动调整','n','免手续费样本','净胜率，95%CI','净均值，95%CI'],rows))
 add('零手续费活动官方日期独立核实，不根据收益挑选。9次正式事件处于活动内，8次达到主首波阈值；活动内只扣4bp假定滑点。其他日期按VIP0情景，未核验全部历史账户费率或报价深度。8/12bp属于低成本情景，不是已验证现货或永续真实成本。净收益是名义本金线性近似，收费资产、手续费复合及借贷均不作虚假精确处理。')
 add('### 公布价失效退出：可检验，但不是利率逆转退出')
 pairs=load('paired_btc_exit_test');rows=[]
 for _,r in pairs[pairs.split=='all'].iterrows():rows.append([H[r.horizon_min],r.n,r.exit_trigger_count,pct(r.net_improvement_mean),f'[{pct(r.ci_low)},{pct(r.ci_high)}]',f'{r.p_value:.3f}/{r.q_value:.3f}'])
 add(table(['退出时点','n','触发次数','对固定持有净均值改善','改善95%CI','p/q'],rows))
 add('规则是确认后首个对齐5分钟BTC收盘穿越P0，下一分钟open退出。4小时平均改善+0.152个百分点，但CI跨零、q=0.438；24小时反而平均少赚/多亏0.427个百分点。此规则容易截断重新回归原方向的事件，不能宣称确认了利率预警。配对样本、原始交易及提前退出实际价格都保留。')
 add('执行价值：可以提前定义并实时识别第一波、回吐及失效；已验证的统计提醒是“高方向保持不等于追单划算”。本样本没有可推荐的无条件15分钟追单规则，也没有证据支持将增长稳健或热CPI方向作为可靠利润过滤器。跨资产确认在实测前不进入交易建议。当前适合把这些固定规则用于记录和前向验证，而不是把少数高胜率格子直接用于实盘仓位。')
 add('## 6. 历史失败案例：错误信号与例外')
 rows=[]
 for date,note in [('2021-02-10','严格增长恶化；冷CPI上涨后反转；24h缺79分钟'),('2022-12-13','4h仍在公布价上方，但追入亏损'),('2023-04-12','严格增长稳健；冷CPI上涨仍反转'),('2024-06-12','明显首波上涨，保持与交易利润脱钩'),('2025-12-18','同比大幅偏冷，月率缺失；4h反转'),('2026-07-14','严格稳健冷CPI的延续反例对照')]:
  r=ev[ev.date==date].iloc[0];rows.append([date,f'{r.headline_yoy_actual:.1f}/{r.headline_yoy_forecast:.1f}',CN[r.growth_strict],pct(r.first_return_30m),pct(r.release_return_240m),pct(r.net_return_240m),note])
 add(table(['日期','Headline同比实际/预期','严格增长','首波15m','公布价至4h','16m入场至4h净收益','含义'],rows))
 add('上述只是完整样本中的解释例子，不替代统计分母。所有92次都进入原始事件库，包含方向错误、门槛不足、极端收益及缺口。2022-11-10处于FTX危机背景，冷CPI后的强反弹不能干净归因于单一通胀机制；同时发布目录和制度标签用于保留混杂，而不事后删除失败案例。')
 add('## 7. 模型局限与未解决问题')
 add('### 来源及实时版本边界')
 add('CPI实际值来自当次BLS官方新闻稿，四项forecast来自事后取得的Investing历史发布事件字段。Headline/Core同比各92组、月率各91组，实际与BLS全部一致。但每次原始调查发布前时间戳、样本构成及08:29快照未独立认证；不能把历史日历字段说成完全封存的原始调查。ISM扩展actual也存在此类版本风险。增长PIT真实版本与这些快照严格分开，所有surprise结果应在更强consensus快照取得后复核。')
 add('没有未来FOMC期货概率快照；最新已完成会议的survey不能替代未来预期。就业/消费宏观模块虽用实时vintage，增长规则是研究固定指标，不能消除市场选择、特殊危机、季节调整和指标之间不同发布时间的误差。能源、住房、服务有实际值，没有每项一致调查预期及需求结构归因。')
 add('### 缺失日期、数量与影响')
 add(table(['缺口','数量/日期','本次影响'],[['正式未发布CPI','2025年10月参考月1次','排除事件宇宙；92而非93'],['MoM实际及预期','2025-12-18，四个字段','仅月率分类缺；同比/价格保留'],['Binance 24h路径','2021-02-10；次日03:41–04:59 UTC共79分钟','24h全样本91；有效首波24h54'],['实际PCE过期','2026-01-13，1项vintage','不强制填充增长'],['失业率3m端点缺失','2026-02-13需要2025年10月','就业OR不明确；严格增长未分类'],['严格ISM初值认证','全部92次未全面认证','严格增长57次未分类；扩展单列'],['Coinbase核验','2019-10-10缺80分钟，2022-05-11缺44分钟','30m可核验91，1h/4h90；不替换主价格'],['2Y/ZT/NQ/DXY及政策快照','全部92日期','H2/H4与跨资产策略未验证']]))
 add('Binance主源全部92次的短窗完整。每次至少获取T0前60分钟至后24小时，92段总原始每日ZIP184个；184个官方SHA256全部一致。重复时间戳0、非法OHLC0、单分钟绝对log变化>0.1的异常标记0。2025开始微秒单位已正确转换，夏令时按纽约时区。缺分钟未插值，路径与终点不混淆。')
 cv=load('crossvenue_audit');rows=[]
 for h in [30,60,240]:
  c=cv[f'direction_agrees_{h}m'].dropna();yes=int(c.astype(bool).sum());kr=cv[f'keep_agrees_{h}m'].dropna();rr=cv[f'reverse_agrees_{h}m'].dropna();rows.append([H[h],len(c),direct_rate(yes,len(c)),direct_rate(int(kr.astype(bool).sum()),len(kr)),direct_rate(int(rr.astype(bool).sum()),len(rr))])
 add(table(['Coinbase核验窗口','n','首波方向一致，95%CI','保持分类一致，95%CI','期间反转一致，95%CI'],rows))
 add('Coinbase与Binance大部分方向一致但不是100%，USDT/美元基差、极小波幅和基准分钟差异可改变边界分类。交叉交易收益只用同一24bp假定成本作价格路径对照，不冒称Coinbase真实费率。所有差异逐事件保存；主要结论仍是Binance现货路径。')
 ex=load('exclude_known_simultaneous');rows=[]
 for _,r in ex[ex.horizon_min.isin([30,60,240])].iterrows():rows.append([H[r.horizon_min],r.n,avg(r)])
 add(table(['排除已识别同时08:30发布事件','n','主顺势净均值，95%CI'],rows))
 add('已识别同时发布22次，来源宇宙仅公开快照的14项宏观系列且主要截止2026-04；70次无记录不等于确认无其他宏观新闻。周四计划初请标签另存，不能用星期代替实际发布时间。BLS实际收入发布常与CPI同时、又由CPI派生，未当作独立冲击。排除这22次只是有限目录敏感性，不是完整控制所有并发事件。')
 add('另外逐次检查未来24小时内实际发生的FOMC决定，标记于事件CSV并单独排除检验。它是事后并发事件审计，未用作发布前增长分组或未来政策概率。2024-06-12是CPI/FOMC同日，4小时窗口止于12:30 ET、早于14:00决定，24小时窗口则包含决定。不能将24小时全部行情归因于CPI。相关日期及排除结果见simultaneous_releases.csv和exclude_simultaneous_and_fomc.csv。')
 add('### 商业数据具体阻碍与成本')
 add(table(['缺产品','所需覆盖','可行渠道与本次状态'],[['真实2Y分钟收益率','92个事件，每次T0−60至T0+24h','可靠债券报价商历史收益率；无现成授权接口'],['ZT与NQ原合约1m OHLCV','CME GLBX.MDP3：2019-01-11至2026-09-12事件窗','Databento / CME DataMine；无授权密钥，报价API401'],['ZT校准','每个事件合约/CTD/交割因子/DV01','期货定义与CTD价格/久期另需；不把价格变动冒充2bp'],['DXY或DX原合约分钟价','相同92事件窗','ICE Futures US合法历史服务；无授权'],['Fed Funds/SOFR期货预期','CPI前与发布后会议对应曲线','CME历史FF/SR3及模型；无封存概率快照'],['严格原始ISM/调查快照','全部历史发布前可知版本','ISM历史服务/原始公告、调查供应商；未完整取得']]))
 add('本次没有证明“数据一定昂贵”，实际阻碍是未取得授权账户与完整产品。Databento当前官方CME Standard价格199美元/月，包含16年以上L0（1m OHLCV等）历史；按量下载也可行，官方有新用户125美元历史数据额度（资格/授权以供应商为准）。两资产×92×1501分钟≈276184条，是取数范围估计，不是账单；按量单价/精确请求报价未授权，故本任务实际成本未知。不能把网页0产品的<$0.01演示报价当任务成本。ICE、原始收益率、CTD与调查的具体费用尚需供应商报价，未虚构美元区间。')
 add('### 统计与执行限制')
 add('Wilson 95%区间用于频率；均值/中位数事件bootstrap10000次；二组概率差Newcombe区间+Fisher；收益差置换10000次。主H1/H3的1h/4h24项检验统一BH；探索检验、策略菜单和退出规则比较分别校正。每格CI是描述区间，不是同时区间；n<10低置信。不能用50%随机方向作为已条件于第一波同侧保持的自然零假设。')
 add('同一事件不同确认窗/阈值/持有时点不是独立观察；年块bootstrap只8块。没有真正历史事前预注册，亦未完全盲法样本外。15分钟等待可能错过主要行情，而5分钟规格交易成本更敏感；这些是观察到的执行结构，不是因果研究。价格OHLC不等于可无限成交，缺盘口/成交容量/延迟轨迹。短策略借贷、永续资金费和现金收益缺失，报告没有声称资金曲线是实际账户账本。')
 add('未完成项只有：H2/H4实测、跨资产策略与利率退出、真实期货政策概率、严格ISM全量原始初值、完全时间认证的consensus、逐笔费用/盘口/借贷。完整CPI/BTC主回测、增长可用范围H1、H3、成本/敏感性/留出与旧研究逐项审计均已完成。')
 add('## 8. 完整事件数据库与数据来源')
 add('### 表G：92次事件简表')
 add('下表是完整CSV的精简视图；Headline/Core列是同比“实际/预期”，首波为15分钟，净收益为确认后16分钟入场到4小时、24bp成本。严格增长“未分类”如实保留。所有四项CPI、增长变量、分钟路径状态、极值、期间/终点触达、净交易和来源字段在table_G_events.csv；所有5/10/15确认窗在event_paths.csv。')
 rows=[]
 for _,r in ev.iterrows():rows.append([r.date,f'{r.headline_yoy_actual:.1f}/{r.headline_yoy_forecast:.1f}',f'{r.core_yoy_actual:.1f}/{r.core_yoy_forecast:.1f}',CN[r.growth_strict],pct(r.first_return_30m),pct(r.release_return_60m),pct(r.release_return_240m),pct(r.net_return_240m),int(r.reverse5_touch_240m)])
 add(table(['正式日期','Headline','Core','严格增长','首波15m','公布价1h','公布价4h','4h净交易','期间反转'],rows))
 add('### 来源清单与实际获取日期')
 manifest=load('source_manifest');times=manifest.loc[manifest.acquired_utc!='derived','acquired_utc'];add(f'原始成功下载日志保存实际UTC时间；本次获取范围{times.min()}至{times.max()}。source_manifest.csv逐文件记录URL、字节数及SHA256，原始失败尝试保留download_errors.csv。全部回测必需的原始数字数据、清洗和结果一并附在复现包，无需联网即可复算。网页会话/广告和非必需文章正文不附，公告保留结构化事实、URL及原始响应哈希；源排除清单在source_exclusion_audit.csv。')
 sources=[('BLS正式CPI档案','https://www.bls.gov/bls/news-release/cpi.htm','日历92次及各次新闻稿链接'),('BLS 2026正式日程','https://www.bls.gov/schedule/2026/home.htm','09-11实际发布/10-14后续计划'),('Investing Headline YoY','https://www.investing.com/economic-calendar/cpi-733','92次公开历史预期字段'),('Investing Headline MoM','https://www.investing.com/economic-calendar/cpi-69','91次月率预期'),('Investing Core YoY','https://www.investing.com/economic-calendar/core-cpi-736','92次核心同比'),('Investing Core MoM','https://www.investing.com/economic-calendar/core-cpi-56','91次核心月率'),('Binance原始1m及校验','https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/','184个ZIP+官方CHECKSUM'),('Binance公开数据格式','https://github.com/binance/binance-public-data','现货2025起微秒时间戳'),('ALFRED vintage','https://alfred.stlouisfed.org/','UNRATE/PAYEMS/PCEC96/DFEDTARU；368原始CSV'),('Investing ISM新订单','https://www.investing.com/economic-calendar/ism-1483','发布事件actual；扩展版本风险'),('Investing FOMC','https://www.investing.com/economic-calendar/interest-rate-decision-168','末次动作，不冒充未来概率'),('宏观二级公共快照','https://github.com/superpilot69/fred-us-macro-open-data','有限同时发布目录及回退；原始调查未认证'),('Coinbase官方历史K线','https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles','92次BTC-USD 1m核验，最大300根'),('Binance零手续费开始','https://www.binance.com/en/support/announcement/detail/10435147c55d4a40b64fcbf43cb46329','2022-07-08 14:00 UTC，BTCUSDT在列'),('Binance活动结束','https://www.binance.com/en/support/announcement/detail/be13a645cca643d28eab5b9b34f2dc36','2023-03-22 00:00 UTC恢复标准费率'),('Binance现货手续费FAQ','https://www.binance.com/en/support/faq/detail/e85d6e703b874674840122196b89780a','普通参考0.1%单边，账户差异未认证'),('Databento官方价格','https://databento.com/pricing','199美元/月及按量历史方案；未实际采购'),('CME DataMine','https://www.cmegroup.com/datamine.html','合法历史产品候选；本次未授权')]
 for i,(name,url,purpose) in enumerate(sources,1):add(f'{i}. **{name}**：{url}。{purpose}。')
 add('所有主统计能从逐事件CSV和Python复算。validation.json记录92次、短窗92、24h91、会计/缺分钟/无未来函数检查通过；r15从原始ZIP独立重算最大误差约4.7×10⁻¹⁴。附184个官方校验比对。README给出安装、一键离线复现、全部字段及未取得数据接口。')
 add('### CPI事件交易决策表（只填已审计结果）')
 rows=[]
 for state in ['stable','deteriorating']:
  b=load('table_B_strict_up');r=b[(b.growth_strict==state)&(b.horizon_min==240)].iloc[0];rows.append([CN[state]+'（严格）','低于预期','BTC首波↑≥0.3%；2Y/NQ未验证','4h保持/反转均有；低置信',rate(r,'keep')+'；反转'+rate(r,'reverse5_touch'),'不据此建立追涨规则'])
 for cl,dirlabel in [('hot','↓'),('cold','↑')]:
  r=hd[(hd.cpi_class==cl)&(hd.horizon_min==240)].iloc[0];rows.append(['不限增长',CN[cl],f'BTC首波{dirlabel}≥0.3%；2Y/NQ未验证','公布价同侧较多，追入收益未证实',rate(r,'keep')+'；净盈利'+rate(r,'net_win'),'暂不把方向保持当交易胜率'])
 r=a[(a.first_wave_filter=='0.003')&(a.headline_yoy_class=='inline')&(a.horizon_min==240)].iloc[0];rows.append(['不限增长','同比符合预期','BTC任一方向≥0.3%；2Y/NQ未验证','4h同侧较多，仍受Core/月率影响',rate(r,'keep')+'；净盈利'+rate(r,'net_win'),'样本15；无稳健正收益规则'])
 for state in ['2Y↓ / NQ↑ / BTC↑','2Y↓ / NQ↓ / BTC↑或↓','2Y↓ / NQ先↑后↓','2Y首波后逆转']:
  rows.append(['未验证','任意',state,'未验证','未验证；已取得联合样本n=0','未验证，不采用此项规则'])
 headers=['公布前经济环境','CPI结果','BTC/2Y/NQ第一波','历史最可能走势','概率及样本量（95%CI）','交易建议'];add(table(headers,rows))
 pd.DataFrame(rows,columns=headers).to_csv(ROOT/'results/cpi_event_decision_table.csv',index=False,encoding='utf-8-sig')
 md='\n\n'.join(sections)+'\n';(ROOT/'report.md').write_text(md);return md

def inline(s):
 s=html.escape(s);s=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',s);s=re.sub(r'`(.*?)`',r'\1',s);return s

class StableCanvas(canvas.Canvas):
 def __init__(self,*args,**kw):kw['invariant']=1;super().__init__(*args,**kw)

def make_pdf(md):
 pdfmetrics.registerFont(TTFont('NotoSC',str(ROOT/'fonts/NotoSansSC-Regular.ttf')))
 pdfmetrics.registerFontFamily('NotoSC',normal='NotoSC',bold='NotoSC',italic='NotoSC',boldItalic='NotoSC')
 styles={
  'p':ParagraphStyle('p',fontName='NotoSC',fontSize=9.4,leading=15,spaceAfter=8,wordWrap='CJK',textColor=colors.HexColor('#24343b')),
  'h1':ParagraphStyle('h1',fontName='NotoSC',fontSize=23,leading=32,spaceAfter=16,textColor=colors.HexColor('#123e48'),wordWrap='CJK'),
  'h2':ParagraphStyle('h2',fontName='NotoSC',fontSize=15,leading=23,spaceBefore=16,spaceAfter=11,textColor=colors.HexColor('#136b77'),wordWrap='CJK',keepWithNext=True),
  'h3':ParagraphStyle('h3',fontName='NotoSC',fontSize=11,leading=17,spaceBefore=11,spaceAfter=7,textColor=colors.HexColor('#123e48'),wordWrap='CJK',keepWithNext=True),
  'cell':ParagraphStyle('cell',fontName='NotoSC',fontSize=7.4,leading=11.1,wordWrap='CJK',textColor=colors.HexColor('#253941')),
  'th':ParagraphStyle('th',fontName='NotoSC',fontSize=7.5,leading=11,wordWrap='CJK',textColor=colors.white),
 }
 story=[];lines=md.splitlines();i=0;width=A4[0]-84
 while i<len(lines):
  line=lines[i].strip()
  if not line:i+=1;continue
  if line.startswith('|'):
   block=[]
   while i<len(lines) and lines[i].strip().startswith('|'):
    v=[s.strip() for s in lines[i].strip().strip('|').split('|')]
    if not all(re.fullmatch(r'[-:]+',s) for s in v):block.append(v)
    i+=1
   n=len(block[0]);cw=[width/n]*n
   # Numeric tables keep date and classification readable; all columns still fit.
   data=[[Paragraph(inline(s).replace('% [','%<br/>['),styles['th'] if j==0 else styles['cell']) for s in row] for j,row in enumerate(block)]
   t=Table(data,colWidths=cw,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#166c79')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f5f6'),colors.white]),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#166c79')),('LINEBELOW',(0,1),(-1,-1),.2,colors.HexColor('#d4e0e3'))]));story.append(t);story.append(Spacer(1,9));continue
  m=re.match(r'!\[.*?\]\((.*?)\)',line)
  if m:
   im=Image(str(ROOT/m[1]));im.drawHeight=im.imageHeight*width/im.imageWidth;im.drawWidth=width;story.append(im);story.append(Spacer(1,9));i+=1;continue
  if line.startswith('### '):sty='h3';text=line[4:]
  elif line.startswith('## '):sty='h2';text=line[3:]
  elif line.startswith('# '):sty='h1';text=line[2:]
  else:
   sty='p';text=line
   while i+1<len(lines) and lines[i+1].strip() and not lines[i+1].strip().startswith(('#','|','![')):
    i+=1;text+=' '+lines[i].strip()
  story.append(Paragraph(inline(text),styles[sty]));i+=1
 def page(c,doc):
  c.saveState();c.setFont('NotoSC',7);c.setFillColor(colors.HexColor('#74858b'));c.drawString(42,A4[1]-27,'CPI × BTC  |  92次事件审计  |  截止2026-10-11');c.drawRightString(A4[0]-42,25,str(doc.page));c.setStrokeColor(colors.HexColor('#d7e2e5'));c.line(42,37,A4[0]-42,37);c.restoreState()
 doc=SimpleDocTemplate(str(ROOT/'report.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=48,bottomMargin=49,title='美国CPI公布后BTC第一波与二次定价历史回测',author='CPI BTC Research',pageCompression=1)
 doc.build(story,onFirstPage=page,onLaterPages=page,canvasmaker=StableCanvas)
 print('report written',len(md),'characters')

if __name__=='__main__':make_pdf(make_markdown())
