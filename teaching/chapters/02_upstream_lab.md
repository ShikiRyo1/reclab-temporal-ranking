## 16 原版实验：先证明自己能复现

### 16.1 这一关要完成什么

这一步的输入是固定版本的公开 notebook 和 MovieLens 100K 原始评分。输出应包括实际运行过的 notebook、四项排序指标、软件版本、数据校验值，以及原值与实测值的对照。完成后，我们可以回答“是否复现了这份代码”，还不能回答“哪种模型在我们的业务中更好”。

本次原版 SAR 与 BPR 已全部执行。八项排序指标与固定 notebook 保存值完全一致。之后的 1M 时间实验另用统一协议比较模型，避免把两种不同考试的成绩放在一起排名。

Recommenders 源自 Microsoft，目前仓库在 recommenders-team。我们使用它公开的 MIT 源码；它不代表 Microsoft 当前内部线上推荐系统。代码中的 SAR、BPR 和原评价函数由原作者提供，固定环境、执行检查、协议审阅与本项目扩展才是我们这次做的工作。

![固定提交页面](H:/Career_AI_Portfolio/projects/01_recommendation_service/teaching/screenshots/01_upstream_commit.png)

图中页面用于核对来源。点击代码页面的提交记录时，注意提交编号必须以 aa833218 开头。我们固定的完整编号为 aa8332189cd495be6ffaa7e1c8054f1c180b5ef3。之后即使仓库 main 更新，本实验仍应使用这个提交。截图证明查看过页面；运行结果另由本地 notebook 和 JSON 记录证明。

### 16.2 打开目录，准备可复现环境

按 Win+E 打开文件资源管理器，在地址栏粘贴下面的项目目录并回车：

```text
H:\Career_AI_Portfolio\projects\01_recommendation_service
```

若使用 VS Code，点 File → Open Folder，选择该目录；再点 Terminal → New Terminal。确认终端是 PowerShell，且当前目录末尾是 01_recommendation_service。下面每条命令单独执行，等待上一条结束再继续。这里的 UI 路径是操作说明，不表示已对你的 VS Code 窗口逐次点击验证。

```powershell
& .\baseline\setup.ps1
& .\baseline\.venv\Scripts\python.exe .\baseline\run_upstream.py
& .\baseline\.venv\Scripts\python.exe .\baseline\check_bpr_math.py
```

第 1 行运行环境准备脚本。PowerShell 的 `&` 表示执行后面的程序或脚本；`.\` 表示当前目录。脚本检查固定源码，创建 baseline/.venv，安装 requirements-lock.txt 中的精确版本，并检查依赖关系。已有正确环境时重复执行只做检查。本次实际输出包含 No broken requirements found.。

第 2 行使用 baseline 自己的 Python 执行完整实验。不要省略前面的解释器路径，否则电脑可能调用另一份 Python，出现“明明安装过却找不到库”的情况。脚本先校验数据和源码，再逐一执行两本 notebook，最后保存结果。只有所有原代码单元运行完成，且指标误差不超过 10^-6，才正常结束。

第 3 行检查 BPR 的数学梯度。它使用一个固定的小例子，不重新训练模型。成功时输出 PASS、解析梯度、数值梯度和最大误差。第 16.6 节会解释为什么需要它。

这三行不依赖激活环境，因而不需要先执行 Activate.ps1，也不应为了运行项目随意修改电脑的脚本执行策略。如果本机策略阻止 setup.ps1，可以按 baseline/README.md 检查 Python 路径和安装步骤，保留原错误文本再排查。

两个环境分开的原因很具体：上游实验需要 NumPy 1.26.4、SciPy 1.13.1、Cornac 2.3.0；项目服务和 1M 扩展有自己的依赖。原版环境放在 baseline/.venv，主项目环境放在 .venv。这不是两次做同一项目，而是避免不同任务抢同一组包版本。

初次安装曾遇到依赖冲突：Cornac 2.3.5 要求 NumPy > 2，固定上游源码要求 NumPy < 2；改用 Cornac 2.3.0 后，SciPy 也必须固定到不超过 1.13.1。我们选择兼容版本，实际跑通，再把所有间接依赖写入 lock。遇到依赖报错时，应找出冲突的约束，而不是一次性升级全部软件。

### 16.3 数据从哪里来，如何检查没有变

下载地址是 GroupLens 官方 HTTPS。原始压缩包位于：

```text
H:\Career_AI_Portfolio\data\movielens\ml-100k.zip
```

它大小为 4,924,029 字节，SHA-256 为：

```text
50d2a982c66986937beb9ffb3aa76efe955bf3d5c6b761f4e3a7cd717c6a3229
```

Hash 可以理解为对文件字节计算的指纹。文件名相同不代表内容相同，hash 才用于核对本次输入是否一致。run_upstream.py 不仅检查 ZIP，也逐字节核对实际读取的 u.data、u.item 是否与压缩包内对应文件一致。若缓存被误改，程序会停止，保留差异供排查。

u.data 每条记录包含用户 ID、电影 ID、评分和时间戳；u.item 是电影元数据。ID 是标识，不能直接当成连续矩阵下标。上游代码会建立 ID 映射，1M 扩展的实现也会显式检查映射。

脚本通过本地缓存参数使用这份数据。它不改原 notebook 文件，而是在内存副本里添加 local_cache_path，再执行副本。报告目录里的 data_manifest.json 记录来源、大小和 hash；*_run_details.json 另外记录训练与测试 DataFrame 的 hash。前者确认原数据，后者确认切分和顺序也相同。

原数据与含示例行的 notebook/HTML 留在本地。公开 GitHub 提供下载步骤、hash 和汇总指标，不直接上传 MovieLens 评分行。数据使用条件保存在本地 MovieLens_100K_TERMS.txt，代码许可证保存在 baseline/UPSTREAM_LICENSE；代码开源不等于数据也可以任意再分发。

### 16.4 两本 notebook 做了什么

在 VS Code 左侧资源管理器中打开 reports → baseline → sar_executed.ipynb，可阅读带实际输出的 SAR 副本；BPR 对应 bpr_executed.ipynb。只想阅读时，双击同目录 HTML 即可，不需要启动 Jupyter 服务。HTML 含原始数据示例，只在本机查看。

如果编辑器提示选择 kernel，选择 baseline/.venv 对应的 Python 3.12。自动执行脚本已经通过项目局部 kernel 完成运行；手动选 kernel 是为了你之后逐格学习。不要把“打开 notebook”当作“重新执行完成”，应查看每个代码单元的执行编号和最后的指标单元。

SAR 原版有 15 个代码单元。阅读时按“导入 → 参数 → 数据 → 分割 → 模型 → 推荐 → 评价”顺序走。下面是模型的关键参数，不必先背代码，把每个参数与其作用连起来：

| SAR 参数 | 本次值 | 为什么有这个参数 |
|---|---|---|
| 数据规模 | 100k | 让 CPU 上完整复现容易检查 |
| 训练比例 | 0.75 | 每个用户随机分出训练与测试 |
| seed | 42 | 固定这次随机切分 |
| similarity_type | jaccard | 根据用户共同交互衡量电影相似度 |
| time_decay_coefficient | 30 | 30 天为半衰期；更近的交互权重更高 |
| timedecay_formula | True | 真正启用时间衰减 |
| normalize | True | 对预测做原评分尺度归一化 |
| top_k / remove_seen | 10 / True | 返回前 10，并排除训练已见电影 |

SAR 可以从两个矩阵理解。A 是用户对电影的亲近程度（affinity），S 是电影间相似度。基本分数是 R=AS：用户对已看电影的偏好，通过相似度传播到其他电影。Jaccard 的分母是两个物品用户集合的并集大小，分子是交集大小。

$$
S_{ij}=\frac{|U_i\cap U_j|}{|U_i\cup U_j|}.
$$

时间衰减以训练期最新时间为参考。单次评分的权重可写作：

$$
a_{ui}=r_{ui}\,2^{-(t_{\max}-t_{ui})/(30\times86400)}.
$$

时间戳单位为秒，所以要把 30 天换成秒。30 天前的评分乘 1/2，60 天前乘 1/4。同一用户与物品若有多次交互，程序会按用户/物品合并。随后还有预测归一化，不能把最终分数直接当作喜欢某部电影的概率。

BPR 原版有 11 个代码单元。它先将评分严格大于 3.5 的记录视为正反馈，因此在整数评分中等价于评分 ≥ 4。过滤后剩 55,375 条，再做全局随机 75/25 切分。它没有采用 SAR 那种逐用户分层切分。

| BPR 参数 | 本次值 | 应怎样理解 |
|---|---|---|
| k | 200 | 用户、物品向量维数，不是推荐条数 |
| max_iter | 200 | 训练轮数 |
| learning_rate | 0.01 | 每次更新迈多大一步 |
| lambda_reg | 0.001 | 抑制参数过大的 L2 约束系数 |
| seed | 42 | 控制数据构造和训练随机性 |
| TOP_K | 10 | 计算评价指标时取前 10 |

注意两个 k 的语义：模型构造里的 k=200 是 embedding dimension，评价里的 TOP_K=10 是推荐列表长度。原 notebook 调用 recommend_k_items 时没有传 top_k，因此先算所有训练用户对未见训练物品的分数，得到 1,272,559 行，再由评价函数选择每用户前 10。我们保留这个行为，没有为了更快而偷偷改成另一套预测协议。

原版 SAR 的训练/测试是 74,992/25,008 行；BPR 是 41,531/13,844 行。SAR 的测试标签包含全部评分记录，BPR 只保留高分。这正是两个原例不能直接比较优劣的原因。统一标签、候选集合和时间切分，是后续 1M 实验需要做的工作。

### 16.5 看哪些结果，怎样确认真的复现

打开 reports/baseline/sar_comparison.json 和 bpr_comparison.json。status 应为 ALL_ORIGINAL_CELLS_EXECUTED，numeric_match_at_tolerance 应为 true。metric_absolute_differences 的四项值本次都是 0。保存原值和实测值是为了能逐项检查，不能仅凭终端一句“成功”验收。

| 原协议 | 指标 | 原 notebook 保存值 | 本次实测 |
|---|---|---:|---:|
| SAR | MAP@10 | 0.244722 | 0.244722 |
| SAR | NDCG@10 | 0.379533 | 0.379533 |
| SAR | Precision@10 | 0.331071 | 0.331071 |
| SAR | Recall@10 | 0.176837 | 0.176837 |
| BPR | MAP@10 | 0.180368 | 0.180368 |
| BPR | NDCG@10 | 0.305190 | 0.305190 |
| BPR | Precision@10 | 0.239032 | 0.239032 |
| BPR | Recall@10 | 0.208660 | 0.208660 |

表格只显示六位小数，JSON 保留完整精度。本次完整精度的差值同样为 0。训练和预测耗时会随电脑负载改变，不能要求和原作者的机器一样，也不能据此宣称我们优化了算法。

Recall 表示找回了测试相关物品的多少；Precision 表示推荐前 10 项中有多少命中；NDCG 还区分命中出现在第 1 位还是第 10 位；MAP 累计各命中位置的 precision。前面章节已有手算例题。这里需额外记住：任何指标都依赖 relevant、candidate、user cohort 的定义。原 evaluator 只统计预测和测试都出现的用户；训练 catalog 外的测试正例仍可能留在分母。这些行为在自己的实验中需要显式说明。

SAR 原 notebook 还输出 RMSE、MAE 等，我们也执行了。不过它们是预测推荐表与测试表内连接后的结果，不能拿来当“全部测试评分回归误差”。原样复现要保留它们；解释结果时要说清楚计算对象。

仓库 README 另有 SAR NDCG=0.3938 的摘要值，和本次固定 notebook 的 0.379533 不同。我们没有挑更高的数作为自己的成绩，也没有假定一定是某个软件版本造成差异。可验证的结论是：这两个 notebook 的保存指标复现成功；不能扩大成仓库所有参考结果都复现成功。

### 16.6 用数学检查一个真实的文档问题

BPR 学习“用户对正例 i 的得分应高于未观察物品 j”。未观察并不证明讨厌，所以这里的 j 是训练采样出的比较对象。令 p 是用户向量，q_i、q_j 是物品向量，b_i、b_j 是偏置，分数差为：

$$
x=p^\top(q_i-q_j)+b_i-b_j.
$$

sigmoid 函数把分数差映射到 0 与 1 之间。最大化 log sigmoid(x)，会鼓励正例比负例得分高。用一半平方范数约定写目标：

$$
J=\log\sigma(x)-\frac{\lambda}{2}\|\Theta\|_2^2.
$$

求导时，最容易混淆的是最大化目标与最小化损失的符号。这里最大化 J，所以使用梯度上升：

$$
z=1-\sigma(x)=\sigma(-x),\qquad
\Theta_{\mathrm{new}}=\Theta+\eta\bigl(z\nabla_\Theta x-\lambda\Theta\bigr).
$$

正则项为什么是负的？只考虑这一项，更新后变成 (1−ηλ)Θ；在小的正学习率下，参数会收缩。如果写成加号，参数反而变大。若原目标写 −λ‖Θ‖² 而不写 1/2，导数应为 −2λΘ，方向仍不改变。

本次检查发现，固定 BPR notebook 的 Markdown 把似然导数写成负号，并在上升更新式中把正则收缩写成加号。这是展示公式的问题。继续查看 Cornac 2.3.0 的实际 Cython 训练源码可见，它正确使用 z=1/(1+exp(x))，再减去 reg×parameter。因此不能把“文档公式写错”说成“训练算法实现错了”。

check_bpr_math.py 把用户、两个物品向量和两个偏置排列为 11 个参数。它对每个参数分别加、减一个很小的 h，比较目标变化：

$$
g_i^{\mathrm{numeric}}
=\frac{J(\Theta+h e_i)-J(\Theta-h e_i)}{2h}.
$$

代码里的 objective 先计算内积与偏置差，再用 −logaddexp(0,−x) 稳定计算 log sigmoid(x)，最后减掉 L2 项。analytic_gradient 写解析结果；for 循环逐坐标算数值结果；最后用最大绝对误差比较。这里 h=10^-6，最大误差为 1.095×10^-10，小于预设的 10^-7 门槛。完整参数和两组梯度保存在 bpr_gradient_check.json，可逐项核对。

一个具体检查是 x=1 时，导数为 +0.2689414214。另一个检查是本例做一次小幅上升更新，J 从 −0.7551046480 增加到 −0.7463151328。这些数字支持“公式与更新方向一致”，不能证明所有训练场景都已穷尽验证。

学习时可以把正则项临时改成加号，在另存的练习脚本中观察范数检查失败，再恢复原式。不要直接改已验收结果文件。这个练习能把微积分、数值方法和实际程序连起来，也给面试提供一个具体例子：我不仅运行了代码，还能区分论文/教程公式、实现和实验输出，并用数值检查验证自己的推导。

### 16.7 这一关怎样讲给面试官

可以用一句话交代：“我先固定开源版本和环境，在 MovieLens 100K 上完整复现 SAR、BPR，八项保存指标一致；审查后发现两份教程的评价协议不同，所以另外设计统一的时间评估，并用有限差分检查 BPR 梯度。”

这句话对应实际文件和输出。不要说“我发明了 SAR/BPR”，也不要仅凭原版分数说“我超过了某公司”。后续章节会把工作推进到时间切分、长尾重排和可运行服务：模型在可比较条件下表现怎样，曝光改善付出了多少相关性代价，以及服务能否稳定返回可解释结果。这些才是完整作品要继续回答的问题。
