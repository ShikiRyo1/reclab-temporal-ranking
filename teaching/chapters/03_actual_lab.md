## 17 亲手重跑完整的1M实验

### 17.1 打开工作目录与终端

本实验的根目录是 H:\Career_AI_Portfolio\projects\01_recommendation_service。先在文件资源管理器地址栏粘贴这条路径并回车；若使用VS Code，选择File → Open Folder，再选择这个文件夹。打开Terminal → New Terminal。终端提示符最后应是01_recommendation_service，而不是用户主目录。后面的相对路径均从这里出发。

打开已有虚拟环境并不需要修改PowerShell执行策略。直接指定解释器更容易排查：命令左端的 .\.venv\Scripts\python.exe 表示“使用当前项目的Python”，后面是要执行的脚本或模块。不要把系统Python、教学文档的bundled Python和此项目的训练Python混成一个环境。

```powershell
Set-Location 'H:\Career_AI_Portfolio\projects\01_recommendation_service'
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
```

本项目环境由uv管理；若环境里没有pip模块，可用uv pip check --python .venv\Scripts\python.exe进行依赖检查。这个差别不影响直接运行Python。需要重建时，先阅读项目README的锁定依赖命令；不要为了消除一条报错就无条件升级所有库。

### 17.2 下载、校验、查看三类文件

prepare_data.py下载官方MovieLens 1M压缩包，并核对固定SHA256；它还核对每个解压文件与压缩包内部对应文件的内容。只检查zip不够：已经解压的ratings.dat也可能被意外改动。

```powershell
.\.venv\Scripts\python.exe scripts/prepare_data.py --data-dir H:\Career_AI_Portfolio\data\movielens
```

运行成功后，H:\Career_AI_Portfolio\data\movielens\ml-1m.zip保留原件；同目录的ml-1m/含ratings.dat、movies.dat、users.dat、README；ml-1m_receipt.json保存下载地址、字节数、hash和解压文件hash。本次zip为5,917,549字节。源码只读取评分与电影表，没有使用users.dat里的年龄、性别、职业和邮编。

ratings.dat每行以双冒号分隔：UserID::MovieID::Rating::Timestamp。movies.dat是MovieID::Title::Genres。电影文件采用latin1解码；随意用UTF-8读取可能失败。MovieID不是从0连续排列的数组下标，必须建立映射。README是使用条件和数据定义，先读它再决定哪些内容可以上传。

下载原始数据与提交代码是两件事。data、artifact及逐用户明细已设置为本地内容。公开仓库保留下载脚本、固定hash、协议和汇总结果，不直接再分发MovieLens数据原件。

### 17.3 配置如何决定一次实验

打开configs/temporal_1m.json。配置不是文档摆设：训练函数实际读取它。要先确定参数，再运行；如果更改配置，就产生新的实验，不应沿用旧结果图。

| 配置 | 本次值 | 它改变什么 |
|---|---|---|
| 正反馈阈值 | rating ≥ 4 | 哪些评分进入正反馈矩阵 |
| 时间位置 | 70% / 85% | 训练与验证截止；同时间戳整体划分 |
| BPR维数 / 轮数 | 64 / 100 | 表达容量和优化轮数 |
| 学习率 / 正则 | 0.01 / 0.01 | 更新幅度与参数约束 |
| 随机种子 / 线程 | 42 / 1 | 控制本次随机过程及执行稳定性 |
| 推荐数 / 候选池 | 10 / 100 | 评估列表长度及重排可见范围 |
| 相关性预算 | 相对NDCG损失 ≤ 2% | 验证集筛选条件 |

固定seed有助于重跑对齐，但它不能证明其他seed也有相同结果。单线程有利于这次复现；没有做线程扩展实验，所以不能把当前训练耗时推断为极限性能。

### 17.4 执行训练并读懂输出顺序

```powershell
.\.venv\Scripts\python.exe -m reclab.train --data-dir H:\Career_AI_Portfolio\data\movielens\ml-1m --config configs/temporal_1m.json
```

先读取数据并切分；再训练三类排序；然后比较验证权重。程序写出selected_config.json和配置hash后，才评估测试集。这个先后次序是防止test tuning的实际约束。日志中的“先保存选择、后测试”比报告里一句“没有泄漏”更有说服力。

本次训练期700,148条、验证期150,029条、测试期150,032条；总和为1,000,209。训练截止为2000-11-22 03:06:26 UTC，验证截止为2000-12-10 04:20:42 UTC。训练模型有4,865个用户向量和3,444个物品向量，每个向量64维。

输出artifacts/model.joblib供服务使用；reports/experiment/summary.json保存汇总；validation_sweep.json保存每个候选权重；data_audit.json保存数据分母；private/保存逐用户指标供本地审计。复跑会重写当前输出；做新实验前先另存配置和报告目录，或按README的版本方式保存，避免把两次实验混为一谈。

### 17.5 先检查人数，再看好看的指标

测试窗口有1,512名评分用户，其中1,486人有正反馈。151条正反馈电影不在训练目录中，不能要求模型预测它们。最终1,485人有至少一个可评估目标，分成922名warm与563名model-cold。

这里的warm指模型中存在训练正反馈向量。model-cold是没有这种向量；用户可能已经给过低分，只是没有训练正反馈。用户1在这次快照中属于model-cold，所以演示个性化时使用用户1161。把“小ID”自动当作老用户是错误的。

主表仅比较同一批922名warm用户；cold另报。若把两组混在一起，组别比例就可能改变总分，导致无法看清排序模型本身的作用。

## 18 读懂已经跑出的结果

### 18.1 四种方法在同一协议下比较

以下是实际执行值，来源为reports/experiment/summary.json；不是预期目标。完整训练执行两次，测试汇总、选参hash及配对区间一致，记录在reproducibility_check.json。

| 方法 | NDCG@10 | Recall@10 | 长尾占比 | 目录覆盖率 |
|---|---|---|---|---|
| 流行度 | 0.207807 | 0.053889 | 0.0000% | 4.0650% |
| 自写SAR-style | 0.224085 | 0.060049 | 0.1193% | 9.1173% |
| BPR | 0.244129 | 0.071576 | 1.8438% | 20.0639% |
| BPR + novelty | 0.240935 | 0.071159 | 2.2777% | 20.9640% |

![实际测试结果图；由保存的1M实验汇总生成，各指标有各自尺度](../reports/experiment/test_metrics.png)

BPR的NDCG相对自写SAR-style高约8.95%。这个比较只针对本次实现、时间窗口和参数；SAR-style不带上游时间衰减，因此不能写成“击败微软SAR”。不同协议的数据量和候选集合也不能直接比较。

### 18.2 扩展真正改变了什么

922名warm用户各返回10部电影，共9,220个推荐位置。长尾位置从170个增加到210个，新增40个；占比增加0.4338个百分点。不同电影从691部增加到722部，覆盖率增加0.9001个百分点。与此同时NDCG相对下降1.308%，所以“提高准确率”不是本次结果。

这项扩展的价值在于把业务取舍写成可以测量的约束：我们愿意支付多少相关性损失，以换取更多长尾内容出现。当前长尾占比仍只有2.28%，并没有解决热门偏置。曝光占比也不能证明用户更满意；需要新的交互证据或在线实验才能回答后者。

### 18.3 为什么选择0.2而不是更大的权重

验证集比较0、0.02、0.05、0.1、0.2、0.35、0.5。原BPR验证NDCG约0.182504，保留98%的下限约0.178854。w=0.2得到约0.181018，满足预算；w=0.35虽然进一步提高长尾，却未满足约束。

![实际验证集权重扫描；选参只在验证集完成，测试数据不参与选择](../reports/experiment/validation_tradeoff.png)

测试结果也恰好低于2%的相对损失，但这是观测结果，不是保证。未来数据发生变化时，同一权重可能越过预算。合理下一步是多时间窗口验证，并预先写好如果越界应如何降回原排序。

### 18.4 配对区间给了什么证据

1,000次用户级paired bootstrap中，重排减BPR的NDCG均值差为−0.003194，95%区间[−0.004972, −0.001335]；长尾占比均值差为0.004338，区间[0.003037, 0.005643]。两个区间方向一致地支持“相关性下降，长尾占比上升”。

Recall差的区间跨过0，因此不应声称Recall明确提高或下降。这里的区间不是“模型有95%概率正确”，也没有覆盖重新训练、换seed、换月份或真实用户曝光选择机制的变化。

### 18.5 分组结果怎样解释

563名model-cold用户使用流行度回退，其NDCG约0.348062、Recall约0.060819。不能据此说冷启动策略胜过BPR，因为这不是同一组用户、同一组目标。它只是这组任务上的可用性基线。

warm用户按训练正反馈条数的中位数52分层，602名高活跃用户的BPR NDCG约0.228992，320名较低活跃用户约0.272606。组别只根据训练信息确定。这提示未来可检查历史长度、目标数量和候选难度，而不是直接宣布某组人“更容易推荐”。

## 19 在网页和API里验证同一个模型

### 19.1 启动本地Docker服务

先打开Docker Desktop，等引擎运行。回到项目根目录的PowerShell执行以下命令。build根据Dockerfile构建镜像，up -d在后台创建并启动服务，ps查看状态。日志包含模型加载失败等诊断；服务未ready时不要跳过检查。

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 80 recommender
```

浏览器地址栏输入 http://127.0.0.1:8011 并回车。这个地址只指当前电脑。compose将宿主127.0.0.1:8011映射到容器8011；它不是公开互联网URL。模型以只读挂载进入/models/model.joblib，应用启动时加载一次，避免每次请求重新读大文件。

### 19.2 跟着真实截图操作

页面左侧“用户ID”输入1161；“推荐数量”保留10；“内容类别”选择全部类别；“长尾重排权重”保留“使用验证集选择的配置”。向下找到“生成推荐”按钮并点击。右侧应出现“个性化BPR”、模型版本和返回列表。

![真实运行截图：1161用户的个性化BPR列表，自动权重为0.2](screenshots/02_personalized.png)

截图中Being John Malkovich排在前列；电影顺序可用于核对这次模型快照。页面推理毫秒数每次会变，不应要求与截图完全相同。显示分数是排序分数，不是观看概率或满意率；0.8126不能读成81.26%的喜欢概率。

接着清空“用户ID”，把“内容类别”改成Drama，再点击生成推荐。空用户走冷启动流行度回退，列表中的每个电影应包含Drama。类型过滤的含义是保留满足所选类型的候选；API接受多个类型时采用任一匹配，网页本身一次选择一个。

![真实运行截图：空用户和Drama过滤触发冷启动回退](screenshots/03_cold_drama.png)

冷启动没有个性化因子，响应中的novelty_weight是实际生效值，被固定为0；requested_novelty_weight另外保留请求或默认配置值。即使请求里给了重排权重，也不能把冷启动结果写成“BPR个性化推荐”。已知用户手动改权重属于探索；离线报告的结论只对应预先锁定的w=0.2。

### 19.3 阅读请求与响应

页面下方的请求/响应区域将当前输入和实际返回结构显示出来。它帮助你把UI动作对应到HTTP契约，而不是只看电影标题。JSON的null表示没有用户ID；空数组[]表示不限制类型；整数k规定希望返回多少项。

![真实请求与响应截图：观察user_id、k、策略、版本及返回数量](screenshots/04_request_response.png)

返回中的requested_k是请求数量，returned_k是实际数量；过滤后可用候选不足时，两者可能不同。model_version说明实际加载了哪份模型；strategy区分personalized_bpr与cold_start_popularity。recommendations中的base_score是原始排序分数，score是当前最终排序分数，不要混为一列解释。

### 19.4 用Swagger发送一个可复查的请求

点击页面右上“API文档”，或打开 http://127.0.0.1:8011/docs。找到POST /recommendations并展开，点击Try it out，在请求框替换为下面JSON，再点击Execute。看Server response中的状态码和Response body。200表示这次请求被处理成功；422说明输入不符合schema。

```json
{"user_id":1161,"k":3,"preferred_genres":[],"novelty_weight":null}
```

![真实Swagger操作截图：请求体与Execute按钮；下方继续查看返回状态和JSON](screenshots/05_swagger_execute.png)

把k改成51再执行，应返回422。把user_id改成null，观察策略改变。这种成对操作让你理解接口规则；无需注册新账号或上传文件。结束后把输入改回合法值即可。

### 19.5 端点各自回答什么

| 地址 | 回答的问题 | 不能据此推断什么 |
|---|---|---|
| /health | 进程还活着，模型是否ready | 所有推荐都正确 |
| /ready | 模型已加载并校验，版本与维度 | 线上业务效果良好 |
| /model | 模型、协议和离线指标说明 | 实时个性化已经更新 |
| /genres | 当前目录有哪些类型 | 所有类型都有足够候选 |
| /metrics | 请求、失败数及最近延迟统计 | 生产环境容量上限 |
| /evidence | 已保存的离线实验汇总 | 在请求期间重新训练 |

metrics统计所有路由，并保留最近最多10,000次响应时长；它不等于专门对推荐路由做的独立压测。500个请求的外部HTTP测试另存在load_test.json，两者统计边界不同。

## 20 如何证明部署可用并保留退路

### 20.1 自动比较HTTP与本地模型

```powershell
.\.venv\Scripts\python.exe scripts/verify_live.py
```

这条命令向真实Docker服务发HTTP请求，再在本地用同一artifact计算推荐。它检查个性化、冷启动、类型过滤和原BPR四种结果的item_id顺序及唯一性，也检查版本、artifact字节hash、主页、OpenAPI、离线证据对应关系、非法输入和监控。本次17项检查全部通过，证据是reports/operations/live_verification.json。

这里比较排序而不是要求浮点数逐位相同：不同系统的BLAS可能在最后几位产生差异。允许末位差异不等于允许电影顺序不一致。要判断容器是否正确加载模型，版本和item_id顺序比“接口返回200”更有用。

### 20.2 真实负载测试怎样读

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_api.py --requests 500 --concurrency 8 --warm-user 1161
```

程序先检查ready，再做10次预热；测量的500次请求不包含预热。375次是已知用户1161，125次是空用户，k均为10。8个客户端线程发请求，报告包含实际墙钟时间、分位数、错误数和模型版本。

| 实测项目 | 本次值 |
|---|---|
| 测量请求 / 并发 | 500 / 8 |
| p50 / p95 / p99 | 23.699 / 30.994 / 68.780 ms |
| 最大延迟 | 72.745 ms |
| 错误数 | 0 |
| 墙钟吞吐 | 约323.98请求/秒 |

这是Windows客户端访问本机Docker的closed-loop测量，持续约1.54秒。它验证了这组小规模请求下的响应和错误处理；不能证明生产SLO、互联网延迟或最大容量。压测结果依赖机器、后台任务、请求分布及连接复用，下一次可能不同。

### 20.3 故障和回滚的逻辑

模型文件缺失、字段不完整、数组形状错配或非有限数值，都应让ready失败，而不是静默返回错误电影。app启动捕捉模型加载异常，保留health供诊断，业务请求返回未就绪。测试用临时artifact制造这些错误，真实模型原件保持可用。

部署前记录镜像标签、代码commit和model_version。替换模型后重启，再执行ready与verify_live；失败时同时恢复旧模型、对应summary.json和镜像配置，否则/evidence会返回409。已验证快照在artifacts/releases/v0.1.0。回滚须以恢复后的请求、版本及hash核对为完成依据。

本次实际运行scripts/check_recovery.py，在隔离的8012端口临时容器中故意不给模型：health返回200且ready=false，ready端点返回503。挂回可信模型并重建临时容器后，ready恢复200，版本与hash一致；临时容器随后清理。证据是recovery_check.json。这证明缺失模型故障与重建恢复，不等于多版本零停机滚动回退。本地Docker也不是云端公开部署。

### 20.4 测试如何帮助你定位错误

数据测试先约束时间、候选和seen；指标测试用可手算的小例子检查分母、折扣与重复项；模型测试检查映射、因子、冷启动与保存后还原；API测试检查边界输入、响应schema和未就绪状态；真实HTTP测试跨过进程与容器边界。

这些层次不能相互替代。NDCG计算正确不证明Docker加载了正确artifact；网页好看不证明没有时间泄漏；500次无错误不证明模型对未来用户有收益。逐层保留证据，才能知道每一个结论来自哪里。

## 21 把项目变成能讲清楚的能力

### 21.1 简历里的事实句

英文实验句：Evaluated popularity, SAR-style and BPR rankers on a 1M-rating temporal benchmark; selected a novelty reranker on validation that increased test long-tail exposure from 1.84% to 2.28% while accepting a 1.31% relative NDCG decrease.

英文工程句：Built a versioned FastAPI recommendation service with input validation, cold-start fallback and Docker deployment; verified ranking parity over real HTTP and measured 30.99 ms local p95 latency across 500 requests at concurrency 8 with zero observed errors.

这里的local、observed、temporal都承担限定作用，不要为了显得更强就删除。不要写“服务了百万用户”：1M是评分条数，数据只有6,040名用户，模型有4,865名warm用户向量。不要写“提升转化”：我们没有转化或在线A/B数据。

### 21.2 30秒讲述与技术追问

中文讲述：我做了一个从离线推荐实验到Docker API的项目。先固定上游代码做基线复现，再用MovieLens 1M建立不看未来数据的时间评估。我比较了流行度、SAR-style和BPR，并用验证集选择长尾重排。在测试里，长尾占比从1.84%增加到2.28%，代价是NDCG相对下降1.31%。最后把模型、过滤规则和版本一起部署，用真实HTTP验证了排序一致性。

技术面试官可能追问：为什么训练低分电影也要排除？为什么cold用户不等于新用户？为什么bias必须跟着因子导出？为什么只比较同一批warm用户？为什么重排前100个不等于全目录优化？如果你能打开相应函数、写出小例子并解释证据，这些句子才真正代表你的能力。

HR通常需要先看懂岗位关联和完成范围。Data Science方向突出协议、指标、误差和取舍；ML/AI Engineering方向突出artifact、接口、输入校验、容器和测试。项目本身不能保证录用，价值在于让这些技能有可查看、可追问的证据。

### 21.3 完成之后还可以延拓什么

第一项合理延拓是rolling-origin评估：保持规则不变，在多个时间边界重复实验，检验w=0.2的稳定性。第二项是更完整的召回/排序分层：当前3,444个电影可以全量打分，百万目录时要评估近邻召回损失、延迟和内存。第三项是明确的在线历史存储，让seen状态独立于冻结模型更新，再测试一致性与回滚。

这些是本项目后续实验候选，当前没有声称已完成。既定第二个项目是Evidence-backed Analytics Agent：围绕SQL、指标定义、来源证据和失败恢复构建分析助手。本项目的结构化接口、数据边界、版本、测试和证据思路会迁移过去；第二个项目有自己独立的分析痛点与验收，不只是为推荐器加一个聊天界面。

### 21.4 你自己的验收练习

不看答案，先解释输入评分如何变成一个API响应；再手算三部电影的NDCG；随后用Swagger发已知用户和空用户两个请求；最后打开summary.json找出NDCG损失与长尾增量。能做到这四步，再尝试修改一个验证权重并预测结果会如何变化。

如果解释卡住，回到对应章，而不是从第一页全部重读。完整源码和逐行伴读用于定位“这一行在做什么”；本手册负责把问题、数学、程序和证据连起来。学习的终点是你能独立重跑、发现错误并讲清取舍，而不是记住截图的点击位置。
