# 服务、网页和操作脚本逐行伴读

完整原代码在可搜索HTML中按真实行号附在说明之后。这里按连续逻辑行解释：多行字典、函数调用与闭括号属于同一语句，合在一起讲；空行只分隔职责，不另造解释。源码的英文docstring说明函数承诺，中文伴读解释它怎样落实，以及哪些事仍没有被证明。

## src/reclab/api.py

### 请求进入之前：契约与产物

**L1–L25。** 模块说明要服务一个可信、不可变的模型产物。annotations延迟类型提示求值；json读取报告；hashlib算精确文件指纹；logging记录加载错误；os读取配置；threading保护共享计数；time分别计时与记录启动时间。deque只保留最近10,000条延迟，asynccontextmanager定义应用生命周期。FastAPI接路由，HTTPException明确返回业务状态码，FileResponse发送网页，Pydantic定义输入输出。validate_model是核心产物校验的别名。ROOT允许环境变量覆盖，在容器里指向/app；WEB随安装包定位静态页面，不依赖当前终端目录。

**L28–L35。** RecommendationRequest声明输入边界。extra=forbid拒绝未知键；examples给Swagger一个1161样例。user_id可为空，否则是至少1的JSON整数；k默认10，是1到50的整数。strict=True拒绝true、数字字符串和10.0被偷偷转成整数。类型列表最多5项，default_factory=list每次新建列表。novelty_weight为空时使用已选配置；数值须在[0,1]且有限。这里的strict仍允许数值0、1，拒绝布尔值和字符串，不能误说“所有整数权重都非法”。

**L38–L47。** RecommendedItem定义每个电影返回项。item_id和title识别电影，genres是字符串列表，score和base_score拒绝非有限数；description明确score不是概率。popularity为训练计数，is_long_tail标记固定目录分组，reason说明这次排序策略。schema能让调用者知道哪些字段可靠存在，但不能证明推荐符合真实用户偏好。

**L50–L59。** RecommendationResponse定义整个响应：模型版本、策略、请求/实际数量、实际/请求权重、推理耗时、推荐数组与适用范围。requested_k与returned_k分开，避免过滤后候选不足仍假装返回够数。novelty_weight是生效权重；requested_novelty_weight保留原请求意图。

**L62–L72。** validate_artifact先调用核心校验，随后检查服务必需字段与schema版本。required减去实际keys得到缺失集合；缺失就抛错。本产物schema_version为数值1；虽然下层局部字符串检查列出了几种形式，先执行的核心校验已拒绝字符串，不能因此说整个加载链接受字符串版本。检查放在ready之前，避免在线请求才发现结构错误。

**L73–L86。** 把ID、因子与流行度转为NumPy数组检查：用户/物品因子都必须二维，列维度相同；行数与ID长度一致；ID不能重复；所有因子有限；流行度长度必须等于物品数且有限。这里的行列检查保护p_u与q_i相乘、metadata定位和候选排名的一致性。它不能验证参数训练得好不好。

**L87–L96。** selected_lambda必须在[0,1]。每个items字典必须有title、genres、item_id；title是非空字符串，genres是非空白字符串组成的列表。后两条来自实际审查发现的漏洞：以前“字段存在但类型错”可能ready成功后在响应中失败。修复把消费者的要求纳入加载契约。

### 加载一次模型，再处理很多请求

**L99–L114。** create_app接受可选模型路径，便于测试注入临时文件；否则先读RECLAB_MODEL_PATH，再回退到项目artifact。lifespan在启动时初始化artifact、错误状态、hash、锁、计数、延迟窗口与启动时间。每个进程拥有自己的状态；多进程部署时这些计数不会自动汇总。

**L115–L125。** joblib加载本项目自己生成的文件；注释提醒pickle能执行代码，结构校验不是恶意文件沙箱。加载后校验，成功才写入app.state；同时计算文件SHA。异常时记录类型与完整日志，保持artifact为空。yield后框架开始服务。FastAPI的标题、版本和description进入OpenAPI说明。

**L127–L140。** measure是HTTP中间件。perf_counter用于单调计时，status先设500，成功收到响应后更新。finally无论正常或异常都执行；锁保护计数与deque。requests_total加1，status≥500才算服务失败，422属于请求被拒绝而非服务器故障。记录毫秒时乘1000。统计覆盖所有路由，不是只统计推荐端点。

**L142–L145。** loaded集中检查artifact是否可用；不可用时抛HTTP503并提示查启动日志，否则返回产物。多个业务路由共用这一关，避免某条接口忘记检查状态。

**L147–L157。** health只回答进程还在及是否ready，因此模型坏了仍可200。ready调用loaded，成功后返回版本、精确hash、schema和用户/物品数；不成功则503。liveness与readiness分离让运维知道该重启进程还是先修复模型配置。

**L159–L168。** model_info返回版本、hash、维度、已选权重、协议与离线指标摘要。get给旧产物缺少的可选说明一个空字典，但required字段仍直接访问。notice保留离线评分数据不能证明业务收益的限制。

**L170–L176。** genres读取所有电影的类型列表，用set去重，再排序返回稳定列表。UI的下拉选项来自这个实际目录；调用者不用猜测大小写或自造类型名。

### 推荐与可观测性

**L178–L187。** POST装饰器绑定响应schema。输入已通过Pydantic，再检查类型名是不是目录子集；未知类型返回422。计时从调用推荐函数前开始。空类型列表转None表示不限制；这次计时不包含完整HTTP收发，也不是压测脚本的客户端延迟。

**L188–L198。** known检查是否存在训练正反馈用户向量。空权重选择artifact中的selected_lambda；已知用户使用请求/默认权重，cold实际权重强制0。输出策略、数量、模型、权重、耗时和列表；round(...,3)只用于显示毫秒，不改变排序。scope随响应保留分数非概率的说明。

**L200–L210。** metrics在锁内复制计数和延迟样本，随后计算p50/p95，避免长计算一直占锁。没有样本时返回null。样本窗口上限10,000，启动时间用来计算uptime。当前metrics请求自身的耗时要等中间件finally才加入，所以本次返回看到的是此前记录。

**L212–L221。** evidence首先要求模型ready。summary缺失时返回pending；存在时用utf-8-sig兼容BOM，解析JSON。报告artifact hash与加载模型不一致就409；这比只比版本字符串更严格，防止旧报告配新模型。验证通过才返回真实汇总。

**L223–L230。** 根路由发送index.html，include_in_schema=False表示不把网页当API列在Swagger。create_app返回应用；模块末尾app=create_app()供uvicorn导入。真正模型加载在lifespan，不在import时执行，使测试和启动边界更清楚。

## src/reclab/web/index.html

**L1–L4。** HTML5声明、zh-CN语言、UTF-8编码与viewport让中文、手机宽度正确处理。title是浏览器标签名，style开始页面样式。它是应用实际页面，不是截图拼出来的演示。

**L5–L10。** CSS变量集中定义背景、正文、弱化文本、分隔线和按钮色。box-sizing让宽度包含边框和padding；body设置字体与行高。main限制阅读宽度，header用flex布置标题和链接；grid用300px表单栏加弹性结果栏。panel提供边框与内边距，把相关输入放在同一容器。

**L11–L19。** label、input、select和button共享字体，字段宽度100%。disabled显示等待状态；message预留高度避免跳动。表格折叠边框，score使用等宽数字便于对齐；pre允许滚动且限高度。屏宽≤760px时grid变单列。CSS不做业务校验，真正范围仍由服务端schema负责。

**L20–L23。** 关闭style/head，建立主体、标题、模型状态、API/模型/证据链接及form。链接target=_blank打开独立标签页。id用于JavaScript找到元素；class用于样式，二者职责不同。

**L24–L28。** 用户ID可以空；数量默认10且1—50；类别初始“全部”，稍后从/genres补齐；权重的空值表示自动，其他选项用于探索。按钮type=submit触发表单事件。hint提醒手动权重不能借用冻结报告的效果。客户端min/max帮助交互，但不能替代服务端验证。

**L29–L31。** 结果区域预留meta和列表，details可展开原始请求/响应JSON。footer保留离线研究与分数含义。使用者既能看电影标题，也能检查到底请求了什么、服务器返回了什么。

**L32–L38。** el封装getElementById。initialize并行请求ready和genres；ready失败就抛错，成功显示版本和目录规模。逐一创建option并写textContent，类型名不会被当HTML执行。catch把连接/模型错误显示给用户，页面不会假装加载成功。

**L39–L43。** submit监听器阻止默认刷新，禁用按钮防止重复点击，清空旧错误状态。把输入字符串转Number，空用户和空权重转null，类别转数组；字符串'0'在JavaScript中是真值，所以权重0仍保留为数字0。fetch发送JSON并读取响应，raw区域用textContent展示可核对结构；HTTP非成功则显示detail。

**L44–L46。** 显示实际返回数、策略、版本、模型内计时和生效权重。创建table及静态表头；每个电影用DOM节点和textContent填入标题、类型和分数，避免动态标题进入innerHTML。只有固定表头用innerHTML。分数toFixed(4)仅控制显示，不改变后台排名。

**L47–L51。** replaceChildren一次替换旧列表；0结果显示明确提示。catch显示失败信息，finally恢复按钮，即使请求失败也可重试。initialize在脚本末尾执行一次，最后关闭script/body/html。当前页面没有账户登录或历史写回功能。

## scripts/prepare_data.py

**L1–L13。** docstring说明官方来源与固定checksum；argparse处理CLI，hashlib核验，json保存回执，urllib获取字节，zipfile解压，UTC记录核验时间，Path管理路径。URL和EXPECTED_SHA256是公开数据的固定身份，不是秘密token。

**L16–L28。** prepare把目标解析成绝对路径并建目录，若zip已存在则复用。下载到.zip.part，按1MiB块写入；完整结束才replace正式文件。walrus运算符把读取结果赋给block，空字节结束循环。网络异常留下part而不是冒充完整zip。

**L29–L38。** 下载或复用后都核对SHA；不一致直接失败。解压前逐个resolve成员路径并检查仍在目标目录内，防止zip路径穿越。ratings.dat不存在才执行extractall，避免每次覆盖已有文件。

**L39–L47。** 遍历非目录成员，用压缩包内字节算hash，再与磁盘对应文件对比。缺失或被改动就报错，不能只依赖zip正确。每个通过的成员摘要保存下来。

**L48–L56。** 回执保存URL、实际路径、字节、hash、是否本轮下载、核验UTC、许可证路径、各成员摘要及不可随意再分发提醒。json缩进便于阅读；返回字典供调用者用。回执记录检查发生过，不代替阅读条款。

**L59–L62。** 命令入口要求--data-dir并转换为Path，调用prepare后打印JSON。示例：python scripts/prepare_data.py --data-dir H:/Career_AI_Portfolio/data/movielens。被import时不会自动下载。

## scripts/benchmark_api.py

**L1–L10。** 导入参数解析、线程池、JSON、平台、单调计时、路径、HTTP客户端与NumPy分位数。docstring说明测量的是实际HTTP响应，不能拿模型内0.4ms替代客户端30ms。

**L13–L23。** run先建立可复用连接池，GET ready检查模型。10次预热全部要求成功，且确认warm_user真的返回personalized_bpr；不满足就失败。这样避免用户1实际上cold却被当作warm压测。

**L25–L36。** request按i%4决定三次warm一次cold，k=10。从发HTTP前计时，成功条件同时要求200、非空结果和正确策略。异常也返回耗时及错误类型，不丢弃慢失败。每条结果是(毫秒,是否合格,状态/异常)三元组。

**L38–L43。** ThreadPoolExecutor最多concurrency个工作线程；pool.map收集所有请求。wall覆盖整轮测量，不包括预热。取每条耗时形成latency，筛选失败形成errors。closed-loop客户端会等线程完成再继续工作，不能据此声称开放流量下的队列稳定性。

**L44–L55。** requests/wall得到观察吞吐，np.percentile给p50、p95、p99，max保留最慢请求，错误样例限制前5条。known/cold数量从实际整数索引计算，即使请求数不是4的倍数也准确。附模型、平台及本地测量限制。

**L58–L74。** CLI默认200次、并发8、warm1161，实际报告用--requests 500。参数数量至少1，否则parser.error。创建报告父目录、写JSON、打印；有错误时退出码1，让外层检查知道失败，而非只留下一个漂亮文件。

## scripts/verify_live.py

**L1–L10。** 引入HTTP、模型序列化、SHA和本地recommend函数。它是部署一致性验证，不负责训练。注释中的trusted提醒只加载本项目生成的artifact。

**L13–L28。** 读取本地artifact及SHA，取第一名有模型向量的用户1161。检查服务ready、版本、精确hash、首页、OpenAPI与evidence数据规模，并确认报告也对应同一个hash。这样同时约束代码可用、模型正确和解释证据匹配。

**L29–L42。** 四组payload覆盖个性化、cold、Drama过滤和weight0原排序。每组先真实HTTP请求，再调用本地函数；比较item_id列表顺序及无重复。BLAS注释解释为什么不要求浮点最后一位完全相同，排序仍必须相同。

**L43–L48。** k=51应422；metrics应记录请求。all(checks.values())只有全部布尔值真才通过，输出带URL、版本、warm用户和scope。不是只看平均值或挑通过项。

**L51–L66。** CLI指定服务、artifact和报告位置。外层try/except把连接失败、JSON错误等写成passed=false的可读报告；创建目录、保存、打印；退出码0代表通过，1代表失败。异常不再让脚本退出而没有审计文件。

## scripts/check_recovery.py

**L1–L14。** docstring说明隔离临时容器。subprocess以参数列表运行docker而非拼接shell字符串，避免路径/参数解释混乱；check_output失败会抛异常，text=True取得文本。ROOT从脚本位置定位项目根，UUID生成不撞名的临时容器。

**L17–L26。** observe最多尝试40次；每次客户端timeout2秒，读取health和ready的状态与JSON。连接尚未建立时等待0.25秒再试；超过次数报错。它是有界启动等待，不是无条件固定睡很久。总等待还受每次网络timeout影响，不应简单说一定10秒。

**L29–L43。** 临时容器使用8012，主服务8011不受干扰。先不挂模型启动并观察，删除这一临时容器；再用同名新容器只读挂回可信artifact并观察。created标记当前是否有本脚本拥有的容器，便于清理。image固定本地构建的career-reclab:0.1.0。

**L44–L55。** 三条验收分别是缺模型health200、ready503、恢复后ready200。报告还保存完整观察、镜像ID与重建恢复限定。写盘打印后，如果不通过再抛错，确保失败证据仍被保留。

**L56–L62。** finally仅删除本次创建的UUID容器；不会查找并删除用户其他容器。main入口运行演练。它没有测试真实流量无中断迁移，也没有证明候选模型与旧模型之间自动回滚。

## tests/test_api.py

**L1–L10。** 导入测试工具与应用factory；fixture使用tiny synthetic数据，不下载1M训练集。json/hashlib用于报告与模型一致性回归测试，api模块导入用于monkeypatch ROOT。

**L13–L28。** artifact fixture手工构建一个用户、三个物品、二维因子、零bias、已见物品10和简单流行度。所有数组、ID映射、标题和类型有明确对应关系，能手算顺序；protocol明确这是合成测试，不混入真实指标。

**L31–L36。** client fixture把artifact写到pytest临时目录，用TestClient的上下文进入lifespan。yield将客户端交给测试，退出上下文做清理。没有覆盖真实model.joblib。

**L39–L50。** 两个测试分别传不存在路径与坏序列化字节；断言alive但notready、推荐503或ready503。它检查启动失败路径，不是通过删除真实模型制造故障。

**L52–L58。** 参数化七种错误输入：k过小/大、负用户ID、权重越界、错字段名和不存在类型；每个都应422。覆盖框架数值schema与业务类型检查两个来源。

**L61–L72。** 未知用户99999应回退、保留版本并返回2项；已知用户1不能推荐seen10，k3只能返回2项。数量不足不是错误，也不应补回看过内容凑数。

**L75–L88。** Drama筛选要求每个返回项含该类型且score有限；重复同一请求的recommendations必须一致，比较时故意不比会变化的耗时。它不证明跨模型版本推荐相同。

**L90–L97。** 访问主页与ready后，metrics应有请求数、延迟和零5xx。这检验中间件路径被调用，不能等同于生产监控完整。

**L99–L115。** 逐个篡改物品因子维度、因子NaN和schema版本，期待相应ValueError。pytest.raises让“必须拒绝坏数据”成为断言，而不是测试自身崩溃。

**L117–L125。** 参数化title=None与genres为字符串，写临时artifact并启动；ready必须503。这是元数据类型漏洞的直接回归保护。

**L126–L138。** monkeypatch把ROOT改到临时目录，先写错误hash报告，要求/evidence409；再写真实artifact SHA，要求200且ready暴露同hash。一个测试同时检查拒绝错配与允许正确匹配，避免修复变成“一律拒绝”。

**L141–L150。** 第一组参数化列出11种类型错误：ID与k的布尔值、字符串、浮点写法，以及权重的布尔值和字符串。每个请求须返回422，detail里的loc还必须指向输入字段。这保护的是请求类型契约；数值看起来像10，不代表调用者发送了JSON整数10。

**L152–L160。** 第二组用0、1、0.2和null验证合法权重仍返回200。测试同时核对个性化策略、请求与返回数量、请求与实际权重，避免严格校验修成“一律拒绝”。fixture默认权重为0，所以该测试中null得到0；真实模型默认是0.2，不能把fixture的输出套到真实模型。2026-10-22新增15个案例，整套由原发布50项增至65项；它们不改变训练结果或证明线上收益。

### 从回归测试走到真实HTTP

打开http://127.0.0.1:8011/docs，展开POST /recommendations，点Try it out。在请求框输入 `{"user_id":1161,"k":true}`，点Execute，再看Server response。本次实际得到422，错误类型int_type，loc指向body/k；true不能被当成整数1。页面上方的curl只是Swagger展示的等价请求，不要求你在PowerShell复制Linux续行反斜杠。

![真实Swagger拒绝布尔k：2026-10-23 02:44:46 UTC，API 0.1.2返回422，错误位置为body/k](screenshots/reaudit_20261022/01_strict_integer_422.jpg)

再把请求框替换为 `{"user_id":1161,"k":1,"novelty_weight":0}`，点击Execute。本次实际返回200、personalized_bpr、requested_k与returned_k均为1。权重0仍被接受，说明修复收紧了非法类型，没有切断合法整数权重。界面版本是0.1.2，模型仍为ml1m-bpr-506d64ca-30794fbd-w0.2；API修复不等于重新训练。

![真实Swagger接受合法整数：2026-10-23 02:45:23 UTC，k为1且权重为0，返回200和1项推荐](screenshots/reaudit_20261022/02_valid_integer_200.jpg)

这两图使用本Chat的IAB实际操作捕获，原始JPEG未改；详细UTC、步骤、SHA和脱敏记录在screenshots/reaudit_20261022/capture_manifest.json。工具build接口不可见，仍标not_exposed。它们只证明这两次调用，其他边界由15项新增回归和独立HTTP检查覆盖。

## Dockerfile、compose.yaml与项目配置

Dockerfile **L1–L4**固定Python基础镜像digest，禁止字节码文件、开启即时日志、限制BLAS/OMP线程，设/app工作目录并复制API依赖清单。**L5–L8**安装精确API依赖，建立UID10001普通用户，复制打包元数据和src，再无依赖安装项目并创建可用目录；不安装Cornac训练堆栈。**L9–L14**切换普通用户，设置模型与项目路径、声明8011，定义ready健康检查，最后用uvicorn监听容器所有网卡。EXPOSE不自动开放宿主端口，映射由compose决定。

compose.yaml **L1–L5**声明recommender服务、当前目录build和本地镜像名；**L6–L9**只绑定宿主127.0.0.1，并只读挂载本地artifact与汇总报告；**L10**unless-stopped让引擎按既定策略重启。只读挂载避免服务意外改模型，但不保证宿主文件永远不变；替换模型后要重启并核对hash。

pyproject.toml **L1–L3**选setuptools构建后端；**L5–L11**定义项目名版本、Python3.12范围和基础依赖；**L13–L15**把训练与测试额外依赖分开；**L17–L21**从src寻找包并打包web HTML；**L22–L24**给pytest设导入路径和tests目录。安装本包后，uvicorn才能导入reclab.api，容器内也能找到网页。

requirements-lock.txt与requirements-api.txt的每一条package==version都固定一个实际安装依赖；左边是发行包名，右边是解析后的版本，不是Python import名的保证。前者用于完整开发训练环境，后者用于服务镜像。完整原文逐行保留在HTML；版本变化应重跑依赖检查、测试及模型加载验证。

configs/temporal_1m.json按层组织dataset、时间比例、positive_threshold、seed、k、candidate_pool、bpr、reranking及bootstrap_samples。BPR的每个键见模型伴读；reranking.weights是有限预注册网格，maximum_validation_ndcg_relative_loss是0.02而不是p值；selection_objective文字必须与train.py实际max排序键相符。所有括号仅限定对象/数组层级，逗号分隔同级键值。

docs/ci-template.yml是未启用的Actions参考流程，不在.github/workflows里执行。理解YAML的on、jobs、steps并不代表本次有GitHub CI运行；仓库权限拒绝已在主手册记明。本地实际执行的pytest与Docker证据独立保留。

### 短配置文件也要知道每一行的职责

src/reclab/__init__.py **L1–L2**：模块说明概括可复现排序与版本化API；__version__保存包版本0.1.2。包版本描述代码发布，model_version描述模型配置，artifact SHA描述文件字节，三者不要互相替代。

configs/temporal_1m.json **L1–L8**：对象起始、数据集名称、训练/验证比例、正反馈阈值、seed、k和重排池大小；**L9–L16**：BPR子对象的维数、轮数、学习率、L2系数、是否bias和线程数；**L17–L26**：重排子对象和七个候选权重（每个独立一行）；**L27–L31**：相对损失预算、选择目标、bootstrap次数及闭括号。当前入口只接受k10/阈值4；要支持其他值需先完整参数化实现与指标标签。

requirements-lock.txt **L1–L50**全部使用“包名==版本”语法；每一行锁住一个依赖，顺序按包名而非执行次序。核心计算是numpy/pandas/scipy，训练是cornac，服务是fastapi/pydantic/starlette/uvicorn，测试是pytest/httpx，绘图是matplotlib/pillow，序列化是joblib/cloudpickle；其余多为这些包的依赖。安装器解析依赖关系，不是把清单当Python逐行执行。完整版本原文在HTML对应50行。

requirements-api.txt **L1–L2**记录uv生成命令；**L3–L58**由版本行与紧随其后的via注释组成。版本行负责约束安装，via注释说明是谁引入它，例如joblib经本项目引入，cloudpickle经joblib引入。多行via列表表示多个包依赖同一包；注释不会额外安装软件。服务清单没有Cornac，不表示数据/数值库也都可以删除。

docs/ci-template.yml **L1–L4**是拟用流程名、push/PR触发和只读contents权限；**L5–L13**定义Ubuntu测试job、checkout、Python3.12及pip缓存；**L14–L17**依次安装锁定依赖、安装项目、运行pytest、构建Docker镜像。这里只解释模板意图；文件位于docs且未启用，所以本次没有GitHub自动运行记录。
