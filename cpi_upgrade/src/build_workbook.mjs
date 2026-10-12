import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=process.argv[2] || path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const p=JSON.parse(await fs.readFile(path.join(root,'results/workbook_payload.json'),'utf8'));
const wb=Workbook.create();const names=['核心结果','月率交叉矩阵','同比交叉矩阵','总体同比核心月率','四项联合状态','暴热暴冷','策略回测','统计与预测','窗口明细','分组日期','92次事件'];
const sheets=Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const out=path.join(root,'deliverables');const previews=path.join(root,'qa/xlsx');await fs.mkdir(previews,{recursive:true});
function col(n){let s='';for(n++;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;}
const namesCN={group_key:'分组键',family:'策略/分组族',label:'分组名称',horizon_min:'目标/持有分钟',confirm_min:'确认分钟',events_n:'条件事件n',valid_n:'有效路径n',missing_n:'缺失路径n',trades_n:'实际交易n',eligible_strong15_n:'初始强首波n',untriggered_or_not_executable_n:'未触发/不可执行n',execution_lag_min:'确认后延迟分钟',exit_kind:'退出口径',cost_bps:'往返成本bp',dates:'全部日期串',up_count:'上涨次数',down_count:'下跌次数',up_rate:'上涨率',down_rate:'下跌率',up_ci_low:'上涨Wilson低',up_ci_high:'上涨Wilson高',down_ci_low:'下跌Wilson低',down_ci_high:'下跌Wilson高',date:'发布日期',year:'年份',monthly_complete:'月率完整(1/0)',four_complete:'四指标完整(1/0)',policy_stage:'此前FOMC方向',growth_strict:'严格PIT增长',growth_snapshot:'扩展快照增长',joint_exclusive:'四项互斥场景',strong_first_03:'强首波>=0.3%(1/0)',exit_only_max_drawdown:'退出点最大回撤',minute_close_max_drawdown:'分钟收盘最大回撤',profit_factor:'利润因子',payoff_ratio:'盈亏比',q_primary:'主要BH q',p:'原始p',hypothesis:'假设',outcome:'检验结果',method:'统计方法',group_a:'A组',group_b:'B组',n_a:'A组n',n_b:'B组n',effect_a_minus_b:'A-B效应(pp/100)',ci_low:'效应95%低',ci_high:'效应95%高',mean_zero_p:'净均值对零p',mean_zero_q_exploratory:'策略筛选BH q',actual_target:'真实目标',model:'模型',split:'时间划分',target:'预测目标',accuracy:'准确率',correct_count:'预测正确数',train_n:'训练n',n:'测试/统计n',brier_score:'Brier损失',log_loss:'Log loss',accuracy_ci_low:'准确率Wilson低',accuracy_ci_high:'准确率Wilson高',historical_holdout_not_unseen:'历史已见留出',regularization_lambda:'L2惩罚',train_last_date:'训练末日',test_first_date:'测试首日',partition:'稳健性分组',url:'BLS实际值来源',t0_utc:'公布UTC',mfe_mean:'MFE均值',mae_mean:'MAE均值',compound_return:'顺序复利回报',group_label:'分组名称'};
const cnField={headline_mom:'总体环比',core_mom:'核心环比',headline_yoy:'总体同比',core_yoy:'核心同比'};
const ruleNames={H1_mild:'总体同比温和意外，顺数据强首波',H1_big:'总体同比显著意外，顺数据强首波',H2_core_mild_cold_up:'核心月率温和冷，BTC强上涨',H2_core_big_cold_up:'核心月率暴冷，BTC强上涨',H3_dual_extreme_hot_down:'双月率暴热，BTC强下跌',H3_dual_other_hot_down:'其余双月率热，BTC强下跌',H4_hy_inline_up:'总体同比符合，BTC强上涨',H4_hy_cold_up:'总体同比冷，BTC强上涨',H4_all_inline_up:'四项符合，BTC强上涨',strong_all:'所有强首波',strong_up:'强首波上涨',strong_down:'强首波下跌',A_strict_monthly:'双月率与首波同向确认',B_strict_core:'核心与首波同向确认'};
function conditionLabel(value){if(ruleNames[value])return ruleNames[value];let text=String(value);for(const [a,b] of Object.entries(cnField))text=text.replaceAll(a,b);return text.replace(/^mom /,'月率 ').replace(/^yoy /,'同比 ').replace(/^hy_cm /,'总体同比与核心月率 ');}
function label(k){
 if(namesCN[k])return namesCN[k];
 for(const [a,b] of Object.entries(cnField)){if(k.startsWith(a+'_')){let end=k.slice(a.length+1);const mapping={sign:'意外方向(-1/0/1)',bucket5:'意外五档',forecast:'预期(%)',actual:'实际(%)',surprise_pp:'意外(pp)',forecast_source:'预期来源URL',forecast_availability:'历史可用性'};return b+(mapping[end]||end);}}
 if(k.startsWith('btc_return_'))return '公布价至'+k.slice(11)+'回报';
 const metrics={release_return:'公布价回报',net_return:'净交易回报',gross_return:'毛交易回报',momentum_net24:'16m入场净回报',net_win:'净盈利',keep:'首波方向保持',fade50_touch:'期间50%回吐',fade100_touch:'期间100%回吐',reverse5_touch:'期间5m反转',reverse5_end:'终点5m反向',fade50_end:'终点50%回吐',fade100_end:'终点100%回吐',new_extreme_touch:'期间创新极值',new_extreme_end:'终点突破极值',re_reversal5:'反手后再次反杀',first_up_reversed_end:'首波上涨后终点跌',first_down_reversed_end:'首波下跌后终点涨',post_reverse_follow_through:'反转后继续反向'};
 for(const [a,b] of Object.entries(metrics)){if(k.startsWith(a+'_')){const suf=k.slice(a.length+1);return b+({n:'n',count:'次数',rate:'率',ci_low:'Wilson低',ci_high:'Wilson高',mean:'均值',median:'中位数',mean_ci_low:'均值95%低',mean_ci_high:'均值95%高',min:'最小',max:'最大',p10:'P10',p25:'P25',p75:'P75',p90:'P90'}[suf]||suf);}}
 return k;
}
function basic(sheet,rows,cols){
 const rg=sheet.getRange(`A1:${col(cols-1)}${Math.max(rows,5)}`);rg.format.font={name:'Noto Sans SC',size:10,color:'#24384A'};rg.format.rowHeight=22;rg.format.verticalAlignment='center';sheet.showGridLines=false;
 for(let i=0;i<cols;i++){sheet.getRange(`${col(i)}1:${col(i)}${Math.max(rows,5)}`).format.columnWidth=i<2?24:19;}
}
function heading(sheet,title,note){sheet.getRange('A2').values=[[title]];sheet.getRange('A2').format.font={name:'Noto Sans SC',size:14,bold:true,color:'#214F6C'};sheet.getRange('A3').values=[[note]];sheet.getRange('A3').format.font={name:'Noto Sans SC',size:10,italic:true,color:'#677686'};sheet.getRange('A3').format.rowHeight=24;}
function grid(sheet,rows,cols,start=5,tableName=null){
 const header=cols.map(label);const data=rows.map(r=>cols.map(k=>r[k]===undefined||r[k]===null?null:k==='date'?new Date(r[k]+'T00:00:00Z'):(k==='label'||k==='group_label')?conditionLabel(r[k]):r[k]));
 const end=start+data.length;const range=`A${start}:${col(cols.length-1)}${end}`;
 sheet.getRange(`A${start}:${col(cols.length-1)}${start}`).values=[header];
 if(data.length)sheet.getRange(`A${start+1}:${col(cols.length-1)}${end}`).values=data;
 const head=sheet.getRange(`A${start}:${col(cols.length-1)}${start}`);head.format={fill:'#285875',font:{name:'Noto Sans SC',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:46,borders:{insideVertical:{style:'thin',color:'#FFFFFF'}}};
 for(let i=0;i<cols.length;i++){
  const k=cols[i];const rg=sheet.getRange(`${col(i)}${start+1}:${col(i)}${Math.max(end,start+1)}`);
  rg.format.horizontalAlignment=rows.some(r=>typeof r[k]==='number')?'right':'left';
  if(k==='date'){rg.setNumberFormat('yyyy-mm-dd');sheet.getRange(`${col(i)}1:${col(i)}${Math.max(end,5)}`).format.columnWidth=14;}
  else if(/_actual$|_forecast$|_surprise_pp$/.test(k))rg.setNumberFormat('+0.0;-0.0;0.0');
  else if(/_rate$|_return_|_return$|^momentum_net24_|_drawdown$|_ci_low$|_ci_high$|_mfe|_mae|accuracy|effect_a_minus_b|mfe_mean|mae_mean/.test(k)&&!(/_return_n$|_count$/.test(k)))rg.setNumberFormat('0.00%');
  else if(/p$|q$|brier_score|log_loss|profit_factor|payoff_ratio|lambda/.test(k))rg.setNumberFormat('0.0000');
  else if(rows.some(r=>typeof r[k]==='number'))rg.setNumberFormat('0');
  if(k==='label'||k==='group_label'||k==='group_key'){sheet.getRange(`${col(i)}1:${col(i)}${Math.max(end,5)}`).format.columnWidth=k==='group_key'?38:43;}
  if(/source|availability|url/.test(k))sheet.getRange(`${col(i)}1:${col(i)}${Math.max(end,5)}`).format.columnWidth=48;
 }
 if(tableName&&data.length){const tb=sheet.tables.add(range,true,tableName);tb.showFilterButton=true;}
 if(end>25){sheet.freezePanes.freezeRows(start);sheet.freezePanes.freezeColumns(Math.min(2,cols.length));}
 return end;
}
// Raw data occupies row 6 onwards; derived counts require completeness to distinguish missing from inline.
const es=sheets['92次事件'];basic(es,98,p.event_columns.length);heading(es,'92次正式CPI事件','四项实际/预期及真实分钟回报；缺失留空。百分数CPI与pp意外使用数值单位，BTC回报使用小数率。');grid(es,p.events,p.event_columns,5,'CPIEvents');
const ec=Object.fromEntries(p.event_columns.map((k,i)=>[k,col(i)]));
function sourceRange(k){return `'92次事件'!$${ec[k]}$6:$${ec[k]}$97`;}
function countFormula(a,b,sa,sb,magnitude=false){const ka=a+(magnitude?'_bucket5':'_sign'),kb=b+(magnitude?'_bucket5':'_sign');const ca=typeof sa==='string'?`"${sa}"`:sa,cb=typeof sb==='string'?`"${sb}"`:sb;let tail='';if(a.endsWith('mom')||b.endsWith('mom'))tail=`,${sourceRange('monthly_complete')},1`;return `=COUNTIFS(${sourceRange(ka)},${ca},${sourceRange(kb)},${cb}${tail})`;}
const statcols=['label','events_n','up_count','up_rate','up_ci_low','up_ci_high','release_return_mean','release_return_mean_ci_low','release_return_mean_ci_high','release_return_median','keep_rate','keep_ci_low','keep_ci_high','fade50_touch_rate','fade100_touch_rate','reverse5_touch_rate','reverse5_touch_ci_low','reverse5_touch_ci_high'];
for(const [name,tag,a,b] of [['月率交叉矩阵','mom','headline_mom','core_mom'],['同比交叉矩阵','yoy','headline_yoy','core_yoy'],['总体同比核心月率','hy_cm','headline_yoy','core_mom']]){
 const sh=sheets[name];basic(sh,120,statcols.length);heading(sh,name+'：全部组合','上方事件数是Excel公式；下方收益及区间是Python统计快照，更新数据需重跑复现程序。');
 sh.getRange('A5:D8').values=[['总体 / 核心','偏冷','符合','偏热'],['偏冷',null,null,null],['符合',null,null,null],['偏热',null,null,null]];sh.getRange('A5:D5').format={fill:'#285875',font:{name:'Noto Sans SC',size:10,bold:true,color:'#FFFFFF'},rowHeight:26,horizontalAlignment:'center'};
 const f=[];for(const sa of [-1,0,1])f.push([-1,0,1].map(sb=>countFormula(a,b,sa,sb)));sh.getRange('B6:D8').formulas=f;sh.getRange('B6:D8').setNumberFormat('0');sh.getRange('B6:D8').format.horizontalAlignment='right';sh.getRange('A10').values=[['该矩阵完整事件合计']];sh.getRange('B10').formulas=[['=SUM(B6:D8)']];
 sh.getRange('A12').values=[['15分钟首波：所有事件，不设幅度门槛']];sh.getRange('A12').format.font={bold:true,color:'#214F6C'};
 grid(sh,p.windows.filter(r=>r.family==='matrix_'+tag&&r.horizon_min===15&&!r.group_key.endsWith('missing')),statcols.slice(0,10),13);
 sh.getRange('A25').values=[['4小时路径：方向保持、回吐和完整5分钟反转']];sh.getRange('A25').format.font={bold:true,color:'#214F6C'};
 grid(sh,p.windows.filter(r=>r.family==='matrix_'+tag&&r.horizon_min===240&&!r.group_key.endsWith('missing')),statcols,26);
 sh.getRange('A38').values=[['五档意外交叉事件数：0.2pp为操作性暴热/暴冷']];sh.getRange('A38').format.font={bold:true,color:'#214F6C'};
 const bins=['暴冷','小幅偏冷','符合预期','小幅偏热','暴热'];sh.getRange('A39:F44').values=[['总体 / 核心',...bins],...bins.map(x=>[x,null,null,null,null,null])];sh.getRange('A39:F39').format={fill:'#285875',font:{name:'Noto Sans SC',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',rowHeight:30};
 sh.getRange('B40:F44').formulas=bins.map(ca=>bins.map(cb=>countFormula(a,b,ca,cb,true)));sh.getRange('B40:F44').setNumberFormat('0');
 const magcols=['label','events_n','up_rate','up_ci_low','up_ci_high','release_return_mean','release_return_mean_ci_low','release_return_mean_ci_high','release_return_median','reverse5_touch_rate','reverse5_touch_ci_low','reverse5_touch_ci_high','net_win_rate','net_win_ci_low','net_win_ci_high','momentum_net24_mean'];
 sh.getRange('A47').values=[['五档组合4h结果：下方顺势基准为所有非零首波，主强首波策略另见策略回测']];
 grid(sh,p.windows.filter(r=>r.family==='magnitude_'+tag&&r.horizon_min===240),magcols,48,tag+'MagnitudeResults');sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(1);
}
const joint=sheets['四项联合状态'];basic(joint,110,statcols.length+1);heading(joint,'四项联合状态','互斥11类合计92；重叠标签不可相加。全部日期见分组日期。');
grid(joint,p.windows.filter(r=>r.family==='joint_exclusive'&&r.horizon_min===15),statcols.slice(0,10),5,'JointStates15');
joint.getRange('A20').values=[['同一互斥场景4h路径']];grid(joint,p.windows.filter(r=>r.family==='joint_exclusive'&&r.horizon_min===240),statcols,21,'JointStates240');
joint.getRange('A37').values=[['重叠场景4h路径；不能作为独立事件相加']];grid(joint,p.windows.filter(r=>r.family==='joint_overlap'&&r.horizon_min===240),statcols,38,'JointOverlap');
const extreme=sheets['暴热暴冷'];const extremedata=p.windows.filter(r=>(['extreme','extreme03','extreme_signal','standardized'].includes(r.family)||(r.family==='single'&&(r.group_key.endsWith('_暴热')||r.group_key.endsWith('_暴冷'))))&&[15,60,240].includes(r.horizon_min));const excols=['label','horizon_min','events_n','valid_n','up_count','down_count','up_rate','up_ci_low','up_ci_high','release_return_mean','release_return_mean_ci_low','release_return_mean_ci_high','release_return_median','fade100_touch_rate','reverse5_touch_rate','reverse5_touch_ci_low','reverse5_touch_ci_high','net_win_rate','net_win_ci_low','net_win_ci_high','momentum_net24_mean','momentum_net24_mean_ci_low','momentum_net24_mean_ci_high'];basic(extreme,extremedata.length+6,excols.length);heading(extreme,'暴热、暴冷与标准化意外','0.2pp为主阈值，0.3pp和仅先前24个误差标准化为敏感性；n<=3极低样本。');grid(extreme,extremedata,excols,5,'ExtremeResults');
const strat=sheets['策略回测'];const scols=['label','family','confirm_min','horizon_min','exit_kind','eligible_strong15_n','trades_n','untriggered_or_not_executable_n','net_win_count','net_win_rate','net_win_ci_low','net_win_ci_high','net_return_mean','net_return_mean_ci_low','net_return_mean_ci_high','net_return_median','payoff_ratio','profit_factor','mfe_mean','mae_mean','minute_close_max_drawdown','exit_only_max_drawdown','re_reversal5_count','re_reversal5_n','re_reversal5_rate','mean_zero_p','mean_zero_q_exploratory','group_key'];basic(strat,p.strategies.length+6,scols.length);heading(strat,'A顺势、B反杀、C延迟策略','主首波>=0.3%；确认后额外1m入场；往返24bp。B/C持有时长是入场后，不是公布后。');grid(strat,p.strategies,scols,5,'Strategies');
const windows=sheets['窗口明细'];const wcols=['label','horizon_min','events_n','valid_n','missing_n','up_count','down_count','zero_return_count','up_rate','up_ci_low','up_ci_high','down_rate','down_ci_low','down_ci_high','release_return_mean','release_return_mean_ci_low','release_return_mean_ci_high','release_return_median','release_return_min','release_return_p10','release_return_p25','release_return_p75','release_return_p90','release_return_max','keep_n','keep_count','keep_rate','keep_ci_low','keep_ci_high','fade50_touch_rate','fade50_touch_ci_low','fade50_touch_ci_high','fade100_touch_rate','fade100_touch_ci_low','fade100_touch_ci_high','reverse5_touch_rate','reverse5_touch_ci_low','reverse5_touch_ci_high','fade50_end_rate','fade100_end_rate','reverse5_end_rate','new_extreme_touch_rate','new_extreme_end_rate','post_reverse_follow_through_n','post_reverse_follow_through_rate','net_win_rate','net_win_ci_low','net_win_ci_high','momentum_net24_mean','momentum_net24_mean_ci_low','momentum_net24_mean_ci_high','group_key'];basic(windows,p.windows.length+6,wcols.length);heading(windows,'八个窗口的完整统计明细','5/10/15/30/60/120/240/1440m。<=15m尚未确认后路径，相关格留空；n=0不填概率零。');grid(windows,p.windows,wcols,5,'WindowResults');
const member=sheets['分组日期'];const mcols=['group_key','family','group_label','date'];basic(member,p.memberships.length+6,mcols.length);heading(member,'每组全部事件日期','一行一个分组-事件映射；不同标签可重叠，同一策略内每事件只计一次。');grid(member,p.memberships,mcols,5,'GroupDates');
const test=sheets['统计与预测'];basic(test,180,18);heading(test,'主检验与时间留出预测','18项主检验BH；模型损失另为探索族。2024-2026历史已被研究过，不是未见前向验证。');
const hcols=['hypothesis','group_a','group_b','outcome','horizon_min','n_a','n_b','effect_a_minus_b','ci_low','ci_high','p','q_primary'];grid(test,p.primary_tests,hcols,5,'PrimaryTests');
test.getRange('A27').values=[['2024-2026历史时间留出：固定L2逻辑回归']];const prcols=['target','model','train_n','n','correct_count','accuracy','accuracy_ci_low','accuracy_ci_high','brier_score','log_loss','regularization_lambda','historical_holdout_not_unseen'];grid(test,p.prediction.filter(r=>r.split==='holdout_2024_2026'),prcols,28,'PredictionHoldout');
test.getRange('A45').values=[['四项组合相对总体模型：负的损失差才是改善']];const dcols=['target','split','metric','n','effect_combined_minus_headline','ci_low','ci_high','p','q_prediction_exploratory'];grid(test,p.model_tests,dcols,46,'IncrementalTests');test.getRange('E47:I54').setNumberFormat('0.0000');
test.getRange('A60').values=[['矩阵探索：每格相对其余事件，81项联合BH']];grid(test,p.matrix_tests,['group_key','horizon_min','n_a','n_b','effect_a_minus_b','ci_low','ci_high','p','q'],61,'MatrixTests');
const summary=sheets['核心结果'];basic(summary,45,12);heading(summary,'CPI四指标与BTC：主要交易结果','92次事件；月率91完整。最强用途是避免错误追单；未发现校正后显著且稳定的正收益系统。');
const keys=['H1_mild','H1_big','H2_core_mild_cold_up','H4_hy_inline_up','A_strict_monthly','strong_all'];grid(summary,p.strategies.filter(r=>keys.includes(r.group_key)&&r.family==='A'&&[60,240].includes(r.horizon_min)),['label','horizon_min','trades_n','net_win_count','net_win_rate','net_win_ci_low','net_win_ci_high','net_return_mean','net_return_mean_ci_low','net_return_mean_ci_high','mean_zero_q_exploratory'],5,'CoreResults');
summary.getRange('A22').values=[['可执行反杀的触发数量与收益']];grid(summary,p.strategies.filter(r=>['strong_all','H2_core_mild_cold_up'].includes(r.group_key)&&r.family==='B'&&r.horizon_min===60),['label','eligible_strong15_n','trades_n','untriggered_or_not_executable_n','net_win_count','net_win_rate','net_win_ci_low','net_win_ci_high','net_return_mean','net_return_mean_ci_low','net_return_mean_ci_high','re_reversal5_rate'],23,'ReversalCore');
summary.getRange('A30').values=[['事件宇宙']];summary.getRange('B30').formulas=[['=COUNTA(\'92次事件\'!$A$6:$A$97)']];summary.getRange('A31').values=[['月率完整']];summary.getRange('B31').formulas=[['=SUM(\'92次事件\'!$C$6:$C$97)']];summary.getRange('A32').values=[['互斥状态合计']];summary.getRange('B32').formulas=[['=SUM(\'四项联合状态\'!$B$6:$B$16)']];
// Verify an actual source change propagates to the count formula, then restore it.
wb.recalculate();
const original=sheets['月率交叉矩阵'].getRange('B8').values[0][0];const old=es.getRange(`${ec.headline_mom_sign}6`).values[0][0];const originalOther=sheets['月率交叉矩阵'].getRange('C8').values[0][0];
es.getRange(`${ec.headline_mom_sign}6`).values=[[1]];wb.recalculate();const changed=sheets['月率交叉矩阵'].getRange('C8').values[0][0];if(changed!==originalOther+1)throw new Error('COUNTIFS source recalculation failed');es.getRange(`${ec.headline_mom_sign}6`).values=[[old]];wb.recalculate();
if(summary.getRange('B30').values[0][0]!==92||summary.getRange('B31').values[0][0]!==91||summary.getRange('B32').values[0][0]!==92)throw new Error('Universe reconciliation failed');
for(const [name,tag] of [['月率交叉矩阵','mom'],['同比交叉矩阵','yoy'],['总体同比核心月率','hy_cm']]){
 const vals=sheets[name].getRange('B6:D8').values;for(let i=0;i<3;i++)for(let j=0;j<3;j++){const r=p.windows.find(r=>r.group_key===`${tag}_${i-1}_${j-1}`&&r.horizon_min===15);if(vals[i][j]!==r.events_n)throw new Error('Matrix count differs from independently computed Python');}
}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2500});await fs.writeFile(path.join(root,'results/workbook_error_scan.txt'),errors.ndjson);
const inspect=await wb.inspect({kind:'table',range:'核心结果!A5:K10',include:'values,formulas',tableMaxRows:6,tableMaxCols:11,maxChars:4500});await fs.writeFile(path.join(root,'results/workbook_inspect.txt'),inspect.ndjson);
for(const name of names){const preview=await wb.render({sheetName:name,range:name==='92次事件'?'A1:L13':name==='月率交叉矩阵'||name==='同比交叉矩阵'||name==='总体同比核心月率'?'A1:H20':'A1:H15',scale:1.5,format:'png'});await fs.writeFile(path.join(previews,name+'.png'),new Uint8Array(await preview.arrayBuffer()));}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(out,'CPI_总体核心交叉矩阵.xlsx'));
await fs.writeFile(path.join(root,'results/workbook_verification.json'),JSON.stringify({sheets:names.length,events:92,monthly_complete:91,count_formulas_recalculated:true,all_matrices_match_python:true,source_edit_propagation_test:true,all_sheets_rendered:true,complex_statistics:'fixed Python snapshots; reproduce to update',rows_windows:p.windows.length,rows_strategy:p.strategies.length},null,2));
console.log('Workbook exported',names.length,'sheets');
