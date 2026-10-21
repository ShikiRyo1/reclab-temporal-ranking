## 22 调试记录与发布边界

### 22.1 一个“ready成功但请求失败”的真实缺陷

初版模型校验只检查元数据有没有title和genres字段，没有充分检查字段类型。构造title为非字符串或genres为异常结构的artifact时，服务可能先返回ready=200，再在推荐或输出序列化中失败。这说明“键存在”不等于“数据满足消费者的契约”。

修复把检查前移到加载阶段：title必须是非空字符串，genres必须是字符串列表，列表成员不得为空白。结构不合法就拒绝进入ready状态，返回503。对应回归测试先构造错误artifact，再断言服务不会宣称就绪。这里的顺序是复现失败 → 找到漏检条件 → 加载前校验 → 测试锁住边界。

### 22.2 报告和模型错配也会误导使用者

另一处问题是/evidence可以读取旧summary.json，却没有确认它属于当前加载模型。接口本身返回200、报告内容也像真的，但两者并不对应。这类错误不会表现为明显异常，反而更容易混进演示和简历。

修复后，启动阶段计算模型文件的SHA256；/evidence将其与summary.artifact.sha256比较。不一致时返回409，明确提示报告属于另一模型。/ready和/model也提供artifact hash。model_version描述配置与数据，文件hash确定具体字节；两者一起保存更容易追踪。

最终本地50项测试通过；17项真实HTTP检查通过。训练入口新增k=10与positive_threshold=4的显式保护；其他值会提前报错，避免只改配置却使固定指标字段或下游阈值悄悄不一致。测试数量只表示当前覆盖的断言，不是“没有任何bug”的证明。

### 22.3 在GitHub上查看已发布内容

打开 https://github.com/ShikiRyo1/reclab-temporal-ranking 。首页README介绍问题、测量值、来源、重跑命令与限制。点击src/reclab看实现，点击tests看校验逻辑，点击reports/experiment看公开汇总。数据原件、模型和逐用户历史没有上传到公共仓库。

![真实GitHub页面截图：已发布的项目源码与说明](screenshots/08_github_published.png)

需要核对历史时，点击commits查看变化；进入Tags寻找baseline-v1可定位基线阶段。后续版本以仓库实际tag和项目交付记录为准。下载源码可点Code → Download ZIP，也可使用git clone；已有本地目录不需要再下载一份。对自己的改动，先git status，再git diff，确认范围后commit。每个assignment保存输入、输出和检查结果，让版本名对应一个可以解释的阶段。

本次GitHub拒绝写入Actions workflow，因为当前OAuth权限没有workflow scope。没有扩大权限或伪造CI结果。拟用流程保留为docs/ci-template.yml，但并未启用Actions；所有已报告检查均为本地真实执行。看到一个YAML文件，不能据此说自动CI已通过。

### 22.4 用真实返回确认成功和失败

Swagger的Execute按钮下面，向下滚动到Server response。下面两张图分别展示合法请求的200与非法k的422。错误不是靠页面文字猜出来的，而是服务器返回的状态与结构。

![真实Swagger返回：合法请求得到200及推荐JSON](screenshots/06_swagger_200.png)

![真实Swagger返回：k超出允许范围时得到422](screenshots/07_swagger_422.png)

### 22.5 学习检查点与下一次改动

输入是固定数据、上游commit、配置与服务请求；输出是复现证据、时间实验报告、版本化模型、API、网页和本套教案。能够在同一协议下比较算法、承认负结果、证明HTTP与离线推断一致，是这个项目比单纯复制notebook更有含金量的部分。

开始下一项改动时，先写痛点、假设、可接受代价和验收指标。新增算法并不自动增加求职价值；只有它解决明确问题，而且你能解释为什么有效或为什么失败，才值得写进履历。本项目下一步可以选择多时间窗口稳定性、可更新用户历史或大目录召回；这些与Agent工具调用的可靠性也有直接连接。

## 23 术语、来源与复查入口

### 23.1 常见英文词怎样对应本项目

| English | 中文与本项目语境 |
|---|---|
| artifact | 模型产物：因子、映射、历史、元数据和版本的整体 |
| candidate catalog | 候选目录：训练期有正反馈的电影集合 |
| eligibility | 可评估资格：未来正例可达且此前未评分 |
| exposure | 展示；这里多指离线推荐位置，不是真实曝光日志 |
| fallback | 回退；没有用户因子时使用已定义流行度策略 |
| leakage | 信息泄漏；预测时不该知道的信息进入训练或选择 |
| ranking parity | 排序一致；两条执行路径返回相同item_id顺序 |
| reranking | 重排；在已有相关候选池中调整最终顺序 |
| readiness | 就绪；模型加载和校验通过才能处理业务 |
| paired bootstrap | 配对自助抽样；同一次抽样保留同用户两种方法 |

### 23.2 每个结论回到哪个文件

| 要验证的结论 | 查阅位置 |
|---|---|
| 用户长期要求与逐条验收 | H:/Career_AI_Portfolio/00_Planning/用户要求与验收标准.md |
| 上游原代码和保存值对齐 | reports/baseline/、baseline/ |
| 正反馈、切分、候选、分母 | reports/experiment/protocol.md、data_audit.json |
| 先选参后测试 | selected_config.json、run.log |
| 主结果与分组、区间 | summary.json、results_and_math_zh.md |
| 两次完整实验一致 | reproducibility_check.json |
| 服务与离线顺序一致 | reports/operations/live_verification.json |
| 负载及恢复 | load_test.json、recovery_check.json |
| 每一行代码及解释 | 代码逐行阅读指南.html、源文件及行号索引 |
| 图片真实来源 | teaching/screenshots/index.csv |

### 23.3 外部依据与使用方式

MovieLens数据定义与使用条件：https://files.grouplens.org/datasets/movielens/ml-1m-README.txt 。阅读时重点看评分语义、数据生成时期和再分发限制；本项目是非商业研究作品集。

固定上游来源：https://github.com/recommenders-team/recommenders/tree/aa8332189cd495be6ffaa7e1c8054f1c180b5ef3 。上游notebook的参数、源代码和保存输出构成忠实复现的依据。主手册的数学讲解经代码与数值核验，不盲目照抄叙述中的公式。

BPR原论文：Rendle et al., BPR: Bayesian Personalized Ranking from Implicit Feedback, UAI 2009；公开论文 https://arxiv.org/abs/1205.2618 。重点理解从三元组偏好到后验目标的转换，不把未观察项直接称为真实负标签。

Cornac实现与参数：https://cornac.readthedocs.io/en/latest/api_ref/models.html#module-cornac.models.bpr 。具体更新还应对照安装版本的源码；教程公式中的正则系数约定与库内部更新频率要区分。

FastAPI自动文档：https://fastapi.tiangolo.com/tutorial/first-steps/ 。本项目运行后的/docs来自实际schema，可验证输入边界和输出字段。Docker端口和挂载说明见项目Dockerfile、compose.yaml及docs/operations.md；本手册截图和命令对应本机核验版本。

### 23.4 怎么使用这套教案

第一次按1—12章建立逻辑，再跟第16—20章亲手操作；第13—15、21—23章用于代码定位、练习、面试与复查。遇到一个术语时看本章，遇到某一行代码时打开可搜索HTML伴读。无需一次读完所有源码，但每个结论都要能找到输入、公式、执行结果和限制。

教学文本先按学习目标与检查点组织，再按术语一致性复查，最后用自然中文润色，保留英文函数名和技术关键词。数学保留LaTeX源并转换为Word原生可编辑公式；真实截图与教学示意图区分标注。最终视觉核验记录放在teaching/qa，不用口头“看起来没问题”替代页面检查。
