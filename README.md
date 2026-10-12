# 美国 CPI 与 BTC 历史事件研究

研究范围：2019 年 1 月至 2026 年 9 月，共 92 次正式 CPI 发布。研究截止日为 2026-10-11，四指标升级复算日期为 2026-10-12。

## 阅读入口

| 文件 | 用途 |
| --- | --- |
| [完整中文报告（Markdown）](deliverables/CPI_BTC_Final_Report.md) | 首选阅读入口，包含结果、定义、五条旧假设复核及局限 |
| [完整报告（PDF）](deliverables/CPI_BTC_Final_Report.pdf) | 适合阅读和分享 |
| [交易规律速查表（PDF）](deliverables/CPI_交易规律速查表.pdf) | 3 页交易员版本 |
| [92 次四指标事件数据库](deliverables/CPI_4指标完整事件数据库.csv) | 每次事件的 CPI、BTC 路径、分组与策略结果 |
| [总体与核心交叉矩阵](deliverables/CPI_总体核心交叉矩阵.xlsx) | 11 个工作表 |
| [暴热暴冷专项研究](deliverables/CPI_暴热暴冷专项研究.csv) | 极端意外、冲突组合及逐事件记录 |
| [第一波与反杀逐笔回测](deliverables/CPI_第一波与反杀策略回测.csv) | 真实分钟路径上的 A/B/C 交易情景 |
| [完整代码、数据与测试 ZIP](deliverables/CPI_BTC_完整代码数据与测试.zip) | 原始完整交付包，可离线复现 |
| [复现说明](deliverables/CPI_回测复现_README.md) | 依赖、运行方法、信号时间和统计定义 |
| [数据来源与完整性审计](deliverables/CPI_数据来源与完整性审计.csv) | 数据来源、获取日期、校验和缺口 |

10 份交付文件的字节数与 SHA-256 见 [DELIVERABLES_SHA256.json](DELIVERABLES_SHA256.json)。代码及研究输入也已从完整 ZIP 展开到 `cpi_upgrade/`，便于直接读取；原始交付 ZIP 保留不变。

## 给 ChatGPT 的读取入口

先读取完整 Markdown 报告和复现说明，再根据问题读取相应 CSV 与源码。需要核对汇总时，使用逐事件库和分组成员日期；不要把同一事件的多个条件、持有期、成本情景当成独立样本。

- [分组与窗口统计](cpi_upgrade/results/group_windows.csv)：294 个组、8 个时间窗口。
- [全部分组事件日期](cpi_upgrade/results/group_memberships.csv)：汇总数字的日期索引。
- [交易分组统计](cpi_upgrade/results/strategy_groups.csv)：顺势、反杀及延迟确认。
- [18 项主假设检验](cpi_upgrade/results/hypothesis_tests_primary.csv)：效应大小、置信区间、p 值及 BH q 值。
- [逐事件字段字典](cpi_upgrade/results/event_field_dictionary.csv)：字段单位和缺失计数。
- [成本与执行延迟](cpi_upgrade/results/cost_latency_sensitivity.csv)：8/12/24/40bp 和延迟敏感性。
- [年份及制度稳健性](cpi_upgrade/results/robustness.csv)。
- [预测模型比较](cpi_upgrade/results/prediction_metrics.csv)。
- [主规格](cpi_upgrade/SPECIFICATION.md)、[源码](cpi_upgrade/src/)、[原始输入及原项目](cpi_upgrade/original/)、[旧研究文件](cpi_upgrade/inputs/)。

本仓库由所有者设为公开。后续可向 ChatGPT 提供仓库链接并指定报告或数据路径。是否能够直接读取整份二进制文件取决于当前会话工具；报告和关键数据库因此同时保留为 Markdown/CSV。

## 复现

```bash
cd cpi_upgrade
python -m pip install -r requirements.txt
python reproduce.py
```

固定随机种子为 `20261012`。完整说明见交付 README。复现过程将重新生成 `cpi_upgrade/deliverables/`；仓库顶层 `deliverables/` 保存本次收到的交付文件。

## 解释结果时必须保留的边界

四项 CPI 分别保留实际、预期及意外；2025-12-18 的两项月率缺失，不用同比代替。历史 forecast 为事后取得的日历记录，不能称为逐次封存的 08:29 调查快照。2024—2026 年为已看过的历史时间留出，不能称为全新前向样本。

方向保持、盘中回吐、5 分钟收盘反转和真实入场后的净盈利是不同指标。主成本 24bp 是参考执行假定，空单借币和资金费不完整。2Y/ZT/NQ/DXY 的授权高频数据仍有缺口，不能把 BTC 反杀回测称为跨资产利率逆转验证。

本次结果具有避免错误追单的历史证据，尚未验证出稳定、可部署的正期望入场规则；小样本场景必须连同样本量和区间一起阅读。
