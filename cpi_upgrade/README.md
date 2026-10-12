# CPI四指标与BTC完整历史回测

92次正式CPI，2019-01-11至2026-09-11；研究截止2026-10-11，升级复算2026-10-12。这里包含真实冻结数据、完整旧获取/清洗代码、新增路径/反杀/延迟回测、统计、预测及测试。不是研究建议书。所有数值可离线复算，不需交易账户、商业行情授权或API密钥。

## 一键复现

Python 3.11或更新版本（本次使用3.12）。解压后进入cpi_upgrade目录：

```bash
python -m pip install -r requirements.txt
python reproduce.py
```

默认先从original/raw里的BLS、Binance ZIP和ALFRED版本重建旧基础数据，再计算全部新增统计并生成两份PDF。固定随机种子20261012，bootstrap/置换10000次。不联网刷新已冻结输入。

已有原清洗结果时，可用 `python reproduce.py --skip-original`；只需统计CSV时加 `--skip-report`。`--refresh`为可选公共下载缺失输入，调用原获取程序并保留现有冻结文件，不自动购买授权数据。次月前向样本不自动进入固定92次研究分母。

XLSX是同一Python结果的便利阅读快照，所有统计数值由CSV直接审计，不依赖Excel。工作簿3×3和5×5计数有Excel公式，修改输入后计数会更新；bootstrap、策略和预测快照须重跑Python刷新。在支持 `@oai/artifact-tool` 的Node环境可运行 `node src/build_workbook.mjs` 或 `python reproduce.py --xlsx` 重新生成同样的11页工作簿；该作者依赖不是统计复算所需的Python依赖。

## 交付与主索引

| 文件 | 内容 |
| --- | --- |
| deliverables/CPI_BTC_Final_Report.md及PDF | 中文完整研究、五条旧假设、真实A/B/C结果、失败案例和决策表 |
| deliverables/CPI_交易规律速查表.pdf | 3页交易员版本，明确小样本和不能追单的条件 |
| deliverables/CPI_4指标完整事件数据库.csv | 92行，四指标、原始来源/可用性、8个回报窗、路径及规范策略收益 |
| deliverables/CPI_总体核心交叉矩阵.xlsx | 11页：结果、三矩阵、四项联合、极端、策略、检验/预测、窗口明细、分组日期、92次事件 |
| deliverables/CPI_暴热暴冷专项研究.csv | record_type=event/summary两种行，组合可能重叠，不能把行数当独立事件数 |
| deliverables/CPI_第一波与反杀策略回测.csv | 5322条条件/确认/期限/延迟情景，主成本24bp，额外8/12/40bp收益列 |
| results/group_windows.csv | 294组×8窗口=2352行，完整命中数/Wilson/分布/均值bootstrap/期间与终点指标 |
| results/strategy_groups.csv | 294组×15策略规格=4410行，主确认及成本；2818个可计算均值对零检验分别BH |
| results/group_memberships.csv | 每个分组的全部日期，一行一个分组-事件映射 |
| results/paths.csv | 92×3确认窗×5后续窗=1380条，1377完整路径 |
| results/hypothesis_tests_primary.csv | 18项事先固定的主对比、效应、CI、p与主BH q |
| results/cost_latency_sensitivity.csv | 8/12/24/40bp和0/1/2分钟额外执行延迟 |
| results/firstwave_threshold_sensitivity.csv | 5/10/15m、0.2/0.3/0.5%和z门槛 |
| results/A_monthly_confirmation.csv | A双月率同向确认在5/10/15m的真实入场、时间留出、剔除2022及48项探索BH |
| results/robustness.csv | 时间留出、剔除2022、逐年剔除、政策/增长/制度及已知并发排除 |
| results/outlier_sensitivity.csv | 5%-95%缩尾、剔除最大绝对事件、逐事件剔除范围；仅探索审计，不用于筛选实盘信号 |
| results/year_block_and_historical_fees.csv | 年度块bootstrap与核验历史免手续费活动情景 |
| results/prediction_metrics.csv及prediction_events.csv | 固定岭逻辑回归的逐事件预测、准确率/Brier/log loss，训练只在此前时间 |
| results/prediction_incremental_tests.csv | 四项相对总体两项的配对差、CI与探索q |
| results/provided_results_reconciliation.csv | 对提供的3份逐组/路径审计CSV全部74项复核 |
| results/test_results.json及numerical_audit.json | 18项新增测试、原始与全部2352组点估计审计 |
| results/raw_sha256_audit.csv | 184/184 Binance官方校验 |
| results/event_field_dictionary.csv | 92行事件库每个字段的类型、单位、缺失计数 |
| results/provided_input_manifest.csv及original_source_manifest.csv | 当前10文件哈希及原数据URL/真实获取UTC，不把读取日期当原取数日期 |
| original/ | 原完整获取/清洗/PIT程序及必要冻结原始数据、旧验证和来源审计 |
| inputs/ | 用户当前10份研究文件，原样保留，便于复核旧数字 |
| SPECIFICATION.md | 计算前固定升级规则；旧历史已读，不是历史预注册 |

Markdown图像使用 ../figures/ 相对路径，完整解压后可直接显示；PDF已嵌入所有图。CSV为UTF-8 BOM，收益小数0.01=1%，CPI实际/预期与意外使用百分数/百分点单位。

## 无未来函数与分母

T0为BLS 08:30 ET，纽约时区自动处理夏令时。分钟时间为K线开始。P0=发布前一分钟close，c分钟确认用T0+c-1 close，闭合时刻T0+c。主A于T0+16 open入场，T0+H open退出，目标方向保持用H-1 close相对P0，二者不是同一收益。

B在15m之后首次完整5m close反向穿越P0，扫描20至240分钟，只取第一次，下一分钟open反向入场。相对持有15/30/60/120分钟和事件4h退出分别保存；后者入场必须早于240。C在30/60分钟仍同侧且此前无完整5m反转，31/61 open入场，再持有60/120/240分钟。没有触发的事件没有虚构成交；trigger_audit逐日期记录未触发和执行状态。

A为顺势基准，真实双月率确认只取 monthly_dual_aligned=1；B核心相符版取 core_aligned=1；其他分组为相同执行规则的条件基准。trades_all含弱首波以便阈值敏感性，主统计统一>=0.3%。不同情景不能合并当作独立交易。

50%回吐以首波沿方向极值E为波幅基准，100%为触达P0；真正反转是完整5m收盘严格跨P0，期间和终点分开。反转后继续反向的条件分母只是目标时点之前已经反转的事件，不是反向入场胜率。

成本主24bp是参考手续费及假定滑点，非账户真实成交。历史BTCUSDT免手续费活动2022-07-08 14:00UTC至2023-03-22 00:00UTC单列往返4bp滑点情景；空单借币费用/资格及永续资金费缺失。MFE/MAE用实际入场后分钟高低及退出open，回撤分分钟close盯市和退出点，100%无杠杆名义仓位、按日期串行。

## 历史可用性边界

四项实际均核对当次BLS；forecast为事后获取的历史Investing日历，不是逐次独立封存的08:29原调查快照。两项环比2025-12-18缺失，保持缺失，新闻稿两个月累计不替代单月。2025年10月参考月无正式发布，92事件不扩为93。2021-02-10后24h缺79分钟，24h整体路径剔除，所有<=4h完整。

严格增长29稳健/6恶化/57未分类；扩展ISM快照68/24，不能把扩展序列当严格PIT。政策阶段是之前最近FOMC决定方向，不是未来会议市场概率。2Y/ZT/NQ/DXY全部92日期缺授权高频数据，旧跨资产机制仍未验证；本次BTC反杀和延迟回测已经完成。

## 统计与检验性质

Wilson95%，均值事件bootstrap10000次，收益差置换10000次，概率差Fisher/Newcombe；18项主检验联合BH，矩阵81项和策略对零为探索族，独立报告q。n<10低、n<=3极低，单例不提供退化均值bootstrap区间。探索稳健性不改主规格，不择最优持有期或成本。

2019-2023/2024-2026是历史时间留出，因为后期旧样本已看过，不能冒称未见样本外。预测模型固定L2=1，训练标准化只取训练样本；同比、月率数据和第一波都有明确时点。完整四指标比较排除2025-12-18，因此预测15m上涨测试n31、强首波4h保持n22。

## 测试

运行 `python src/test_upgrade.py`，本次18项通过，包括价格基准保持但交易亏损、盘中触碰不构成5m反转、真实下一分钟反向入场、缺分钟拒绝、空方向反弹亏损、浮点分类/夏令时、92事件及缺失、所有5322条入出价与信号先后、735个原始ZIP收益、184校验、366个BLS实际值、滚动误差只用先前事件、预测时间顺序。`output_audit.py`另独立核对2352组全部点估计；原旧验证也通过。

随机种子和依赖固定；不同平台优化器浮点末位可能略异，12位数字以内按1e-10收益容差核验。不会输出未经观测的胜率或概率。
