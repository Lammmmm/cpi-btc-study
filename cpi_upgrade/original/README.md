# 美国CPI与BTC事件研究：一键复现

截止日期2026-10-11；实际发布92次，2019-01-11至2026-09-11。本包含冻结的原始公开数据，不需要联网、交易账户或API密钥即可复算BTC、CPI和增长结果。未获取的2Y/ZT/NQ/DXY不被填造。

## 运行

推荐Python 3.11或更新版本。在解压后的cpi_study目录运行：

```bash
python -m pip install -r requirements.txt
python reproduce.py
```

该命令从原始文件重新清洗、回测、汇总、交叉验证、审计并生成中文Markdown及PDF。通常数分钟；统计bootstrap/置换均10000次，固定随机种子20261011。无网络环境已安装依赖时直接运行第二行。仅复算统计可用`python reproduce.py --skip-report`。

可选`python reproduce.py --refresh`从公开源补下载缺失文件；已有文件保持冻结，不覆盖历史快照。若想重新取得某个原始文件，先备份并移走对应文件。网页结构变化可能影响新下载，完整冻结输入仍可离线使用。报价与数据授权不自动购买。

## 文件

| 文件/目录 | 内容 |
| --- | --- |
| report.md / report.pdf | 完整中文报告，附92个事件简表 |
| SPECIFICATION.md | 计算结果前固定的规则；不是历史预注册 |
| raw/bls、raw/btc、raw/vintages、raw/coinbase | BLS官方新闻稿、Binance ZIP及官方CHECKSUM、ALFRED事件前一天vintage、Coinbase原始1m数据 |
| data/investing_*.json | 从公开日历页提取的四项CPI、ISM、FOMC事件记录；不包含页面会话与广告信息 |
| data/events_cpi.csv、data/growth.csv、data/btc_*.csv.gz | CPI记录、增长分组、事件分钟价格 |
| results/table_G_events.csv | 92行完整逐事件数据库，汇总结果的追溯入口 |
| results/event_paths.csv | 1104行：92事件×3确认窗×4退出窗；1101行可用 |
| results/table_A*.csv、table_B*.csv、table_C*.csv | 不同CPI口径、增长分组及意外幅度的完整统计 |
| results/H1_first_wave.csv | 冷CPI×严格/扩展增长的5/10/15分钟第一波方向，含安静波动与有效上涨分母 |
| results/table_D_cross_asset.csv、table_E_rate_reversal.csv | 明确未验证；n=0指取得的联合样本为零，不是概率零 |
| results/table_F_strategies.csv、trades.csv | 固定策略菜单、成本/时间分组、交易记录 |
| results/historical_fee*.csv | Binance历史BTCUSDT零手续费活动的成本敏感性 |
| results/hypothesis_tests.csv、table_A_tests.csv | 效应量、置信区间、原始p与BH校正q |
| results/sensitivity.csv、leave_one_year_out.csv、year_cluster_bootstrap.csv | 确认窗、阈值、逐年剔除、按年bootstrap |
| results/execution_latency_sensitivity.csv、regime_sensitivity.csv | 确认后0/1/2分钟延迟及制度标签敏感性 |
| results/cold_components.csv、surprise_growth_interaction.csv | 核心/能源诊断及增长交互的探索结果 |
| results/legacy_audit.csv | 对旧PDF全部14个事件的独立重算及其入场后收益 |
| results/legacy_strategy_statistics.csv | 旧规则净收益置信区间及时间留出，不因低胜率掩盖正样本均值 |
| results/simultaneous_releases.csv、exclude_simultaneous_and_fomc.csv | 有限同时08:30发布目录、24h内FOMC并发审计及排除敏感性 |
| results/btc_audit.csv、crossvenue_audit.csv、growth_audit.csv | 缺失分钟、跨交易所及vintage完整性审计 |
| results/growth_calendar_window_audit.csv | 按准确日历月份审计失业率/PCE端点及NFP连续月份；不跨停摆缺口替代 |
| results/source_manifest.csv、source_checksum_audit.csv | 文件SHA256、URL、实际获取UTC及184个官方哈希验证 |
| results/missing_data.csv、cross_asset_missing.csv、download_errors.csv | 日期级缺口及下载失败日志 |
| results/event_field_dictionary.csv | 全部事件字段、类型、单位、缺失数 |
| src/ | 获取、清洗、回测、统计、审计、报告代码 |
| fonts/、fonts/LICENSE | PDF所需Noto Sans SC字体及OFL许可 |

## 口径与无未来函数

所有UTC由`zoneinfo.ZoneInfo('America/New_York')`和正式08:30 ET换算；夏令时为12:30 UTC，冬令时为13:30 UTC。原始K线时间是**分钟开始**，2025起Binance现货时间戳为微秒，此前为毫秒。

P0为T0前一分钟收盘。确认c=5/10/15分钟，确认价是T0+c−1分钟的收盘，闭合时刻T0+c。主规格c=15、绝对第一波≥0.3%。交易等待额外一分钟，T0+c+1的open入场；T0+H的open退出。方向保持取T0+H−1分钟close相对P0，不是入场后盈利。

宽表G的`first_return_30m/60m/240m/1440m`都指15分钟第一波，后缀是该组后续目标窗口；`release_return_30m`才是P0至30分钟回报。5/10分钟第一波在event_paths.csv按confirm_min读取。z标准化用发布前60个分钟收盘产生的59个相邻1m log收益样本标准差，ddof=1。

`first_reverse5_min_*`或`baseline_exit_min_*`为空也可能表示没有触发，而非价格数据缺失；结合窗口status和reverse5_touch判断。2Y_return_*是未验证的空占位，不能按分数收益率填入2Y变化；真实利率接口用rate15_bp/收益率百分点差。

50%回吐以第一波沿信号方向的最高/最低极值E定义；确认后OHLC触达P0+0.5(E−P0)计期间触达。100%回吐计触达P0；真正反转须确认后完整5m收盘严格穿越P0，5m块与T0对齐。`*_touch`是期间发生，`*_end`是目标时点确认。确认时已经回吐一半另记`fade50_at_confirm`；不会把此后触达误说成确认前从未回吐。新高/新低由确认后极值严格超过E判定。5m数据能确定先后到5分钟粒度，分钟OHLC内极值顺序不可知。

gross_return=direction×(exit/entry−1)，net_return=gross_return−0.0024。主成本为VIP0参考每边10bp手续费+假定每边2bp滑点；8/12/40bp另测。实际账户VIP/BNB折扣、成交簿、借贷利息及永续资金费未取得，故称成本调整情景，不能称历史真实成交净值。手续费扣减是线性名义本金近似；不是含收费资产变化的精确逐笔账户账本。

历史活动补充：2022-07-08 14:00 UTC至2023-03-22 00:00 UTC，BTCUSDT maker/taker免手续费；涉及9个CPI，8个满足主第一波门槛。`historical_fee_scenario_net`在这段使用往返4bp（仅假定滑点），其余24bp。依据为已核验的Binance公告；结构化事实、URL、获取日期和原始HTTP响应SHA256保存于data/fee_schedule_facts.json。非必需文章正文不附，冻结事实可直接离线复现。

现货做多单独统计；做空只是假设能借BTC的方向收益，不包含借贷成本/资格，不是可保证执行的现货空策略。全仓无杠杆、每次只在事件窗口持仓；最大回撤分别给出事件退出点和分钟收盘盯市。未含闲置现金利息、税务、OHLC内顺序和未实现风险的逐笔精度。

## 宏观数据

CPI实际值来自该次BLS新闻稿，四个forecast来自公开Investing历史日历中的发布事件记录；YoY共92组，MoM91组。二级公共仓库只有缺项回退及有限同时发布目录用途。四项实际值逐一核对BLS；没有把前值当预期。

这些是**事后获取的历史forecast字段**，没有逐次独立封存的发布前08:29调查快照，也没有调查样本及截止时间。因此surprise分类可复现，但其严格原始时点来源仍有残余风险。无法声称所有forecast均经过独立发布前时间认证。2019年1–7月7次均有统一日历字段，不再排除。

失业率UNRATE、非农PAYEMS、实际PCE PCEC96及联储目标上限DFEDTARU均取CPI前一天ALFRED vintage，验证列头的YYYYMMDD。各时点使用当时已知的历史修订，绝不使用研究日最终修订值。PCEC96序列是实际消费水平，不是名义零售。观察月份截止月末距事件≤95天才可用，2026-01-13该项过期不填补。

就业恶化=(失业率较3个月前上升≥0.2pp)或(最近3个月NFP平均<最近6个月平均)。消费恶化=实际PCE水平3m变化≤0。ISM新订单恶化=最近3m平均<50且低于前3m平均。至少两项恶化才定义增长恶化。未知维度用可能恶化数上下界；不能判定则未分类。严格组不使用未全面核验原始vintage的ISM日历actual；扩展组使用对应发布的历史日历actual，但单独注明风险。

三个月严格指日历月份，不以四条非空记录替代。2025年10月失业率缺失，2026-02-13所需3m端点未知；非农子项不恶化不能把“失业率未知 OR 非农不恶化”判为就业稳健。故严格组最终29稳健/6恶化/57未分类，扩展68/24。就业OR使用逻辑上下界；NFP3m/6m平均须所需月度level变化连续。停摆窗口测试包含在validate.py。

政策阶段仅为CPI之前最近一次FOMC决定方向hiking/cutting/pause，不等于未来会议市场预期。末次FOMC actual与ALFRED上限92/92吻合；末次会议forecast是该次决定的旧调查，不替代CPI发布前未来会议期货隐含概率。疫情、高通胀、快速加息是独立制度标签，不代替增长状态。

## 统计

二元率Wilson 95% CI；均值/中位数非参数事件bootstrap 10000次；概率差Newcombe区间与Fisher检验；收益差10000次置换。主H1/H3的1h、4h比较统一BH校正，其他探索家族各自BH。不同表的描述CI不是同时置信区间，多次阈值不是独立样本。检验菜单与q字段见原表；报告不挑最佳参数宣称优势。

时间留出2019–2023/2024–2026；因已阅读旧PDF中部分后期事件，不能称真正未见样本。按年bootstrap仅8个年块，CI仍不稳定；逐年剔除完整提供。n<10为低置信。收益因果性不成立，CPI只是共同时间锚。

## 必须保留的缺失

正式事件92而非93：2025年10月**参考月**CPI未发布，不对应一笔交易；2025-10-24发布的是延迟的9月数据，仍计入。2025-12-18的11月数据无10月比较基数，所以两项MoM actual/forecast为空；YoY和BTC保留。2026年9月参考月将在2026-10-14发布，截止日尚不可纳入。

2021-02-10的24h窗口缺79分钟，2021-02-11 03:41–04:59 UTC；仅24h整条路径剔除，不保留有终点却缺路径的假完整结果。所有92事件的30/60/240分钟均完整。Coinbase交叉核验2019-10-10、2022-05-11各有80、44个缺失分钟，不拼接进Binance主样本。

H2/H4、真实2Y逆转退出、NQ由涨转跌、DXY及未来FOMC期货概率没有观测样本。缺口覆盖全部92日期，逐日列于cross_asset_missing.csv。环境无Databento授权密钥；合法公开GitHub候选仓库只暴露代码/换月表，没有可核验的完整NQ原始分钟报价。官方CME Databento/CME DataMine、ICE历史服务是候选渠道，未采购。Databento官方Standard公开价格199美元/月含L0长历史（具体产品授权以供应商为准）；按量精确报价接口未授权(401)，不能虚报本任务实际美元费用。ZT替代2Y还需要逐合约CTD/DV01，不自动把tick折成2bp。

若已有真实已授权文件，按input_schema/cross_assets.csv字段填入分钟数据后执行：

```bash
python src/cross_asset.py path_to_authorized_cross_assets.csv
```

该模块为待验证接口，当前没有历史实测输出，不属于已完成H2/H4。rate_pct必须是真实2Y分钟收益率（单位百分数），或另行验证的带calibration_id数据；单独ZT价格不能填rate_pct。模块使用30/60分钟landmark，先排除BTC已经反转，避免用未来利率状态预测过去BTC。若改阈值/交易规则，须作为新探索规格报告。

## 完整性

src/validate.py包含方向保持但追入亏损、空方向反弹、5m反转、缺分钟拒绝、停摆日历端点等会计测试，全部通过；独立从92个原始ZIP重算r15，与CSV最大误差<5×10^-14。184个Binance ZIP与官方SHA256逐一吻合。validation.json给出测试输出。source_manifest.csv保存随包输入的获取时间和文件哈希；download_log.jsonl保留每次已发生获取，包含不分发的诊断网页。source_exclusion_audit.csv保留这些网页的URL与响应哈希；不要把运行日期当成原始下载日期。

图表和PDF用Noto Sans SC（OFL）生成；未附用户原PDF，原研究14事件逐项复核结果在legacy_audit.csv。
