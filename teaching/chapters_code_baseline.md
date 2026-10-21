# P1 上游复现与数学核验代码伴读

本节覆盖 baseline/run_upstream.py 的 L1–L205，以及 baseline/check_bpr_math.py 的 L1–L65。完整代码已放在本伴册 HTML 的“完整源码”区，可以按文件名和行号定位。空行用于分段，单独的括号收尾归入所属语句。下文解释每一组语句的输入、动作、输出和失败条件，不把第三方训练器的全部源码误称为我们自己实现的代码。

## A. run_upstream.py：让复现有可检查的证据

### 路径、版本和小工具

**L1–L12。** L1 的模块说明限定任务：执行固定上游 notebook，保留原件并标明本地适配。L2 延迟类型标注解释。argparse 读取命令行参数，hashlib 算文件摘要，json 保存结构化结果，os 读取和设置环境变量，Path 组合路径，platform 记录操作系统，shutil 复制许可证，subprocess 调用 Git 和 pip，sys 提供当前解释器，time 测量执行耗时。导入这些库没有开始训练。

**L14–L23。** COMMIT 是唯一接受的源码版本。ROOT 从当前脚本的绝对位置往上两层得到项目根目录，不依赖终端恰好在哪个目录。WORKSPACE 优先使用 P1_WORKSPACE 环境变量，否则按当前 H 盘项目结构找到工作区根。UPSTREAM、DATA、REPORT 分别指向外部源码、原始数据和结果目录。NOTEBOOKS 把简短名字 sar/bpr 映射到固定仓库内的真实 notebook 文件，后续不会临时搜索一个名字类似的文件。

**L25–L29。** sha 输入 Path，读取原始字节并输出 SHA-256 十六进制摘要。这里的文件较小，直接 read_bytes 简单可审计；处理很大的模型文件时应分块读取。write_json 输入目标路径与可序列化对象，输出缩进两格、UTF-8 编码的 JSON。ensure_ascii=False 保留中文；结尾加换行便于文本工具读取。它不自动创建父目录，所以调用前 setup 必须先准备 REPORT。

**L31–L38。** metadata 输入 notebook 对象，输出“指标名 → 保存值”的字典。L33 遍历单元，L34 读取输出列表；Markdown 没有 outputs 时用空列表。L35 只读取上游 store_metadata 写出的专用 MIME 类型，不从屏幕显示的六位小数反推完整指标。L36–L37 跳过不存在的记录，按 name 保存 data。若原 notebook 缺少需要的指标，后面按键读取会报错，不会悄悄补零。

### setup：先验证输入，再执行模型

**L40–L45。** setup 不训练模型。truststore.inject_into_ssl 让 HTTPS 连接使用本机操作系统证书库，并保留证书验证；这是本机证书链问题的修复方式，不是设置 verify=False。随后导入 requests，创建数据和报告目录。parents=True 允许父目录尚不存在，exist_ok=True 允许重复运行。

**L46–L50。** subprocess 的参数用列表传给 Git，没有拼成一整段 shell 字符串。rev-parse HEAD 返回当前提交，strip 去掉尾部换行；不同于 COMMIT 就抛 RuntimeError。接着 git diff --exit-code 比较相关源码和两本 notebook 是否仍与固定提交一致。check=True 会把非零返回码变成异常。这能防止“提交编号没变，但工作区源码被手改了”仍被当作原版复现。

**L51–L58。** 指定原始 ZIP 路径和官方 HTTPS URL。只有本地不存在时才下载。timeout=(15,120) 分别限制连接和读取等待；raise_for_status 拒绝 HTTP 错误响应。先写 .zip.part，完整响应落盘后再 replace 为正式文件，避免把下载一半的文件当作完成。此处 replace 操作只针对脚本新下载的临时文件，不删除用户目录。

**L59–L65。** expected_sha 是已核实原始 ZIP 的固定摘要。sha 不匹配就停止，防止同名但不同内容的数据进入实验。ZipFile 用上下文管理器打开并自动关闭；testzip 检查内部 CRC 完整性，有损坏成员就报错。固定 SHA 确认预期字节，CRC 检查压缩文件内部一致性，两者作用不同。

**L66–L75。** 从 ZIP 取原始 README 留作本地使用条件。随后仅处理 u.data 与 u.item。expected_bytes 来自已校验 ZIP；如果已有缓存的字节不同，报错并保留文件供排查。如果文件缺失，才写出原始字节。最后计算两份实际读取文件的摘要。只校验 ZIP 而忽略解压缓存是不够的，因为上游 loader 可能直接复用缓存。

**L76–L82。** data_manifest.json 记录来源、实际路径、字节数、ZIP 摘要、解压文件摘要和不可直接公开原数据的提示。这里输出元数据，不输出评分行。copyfile 复制上游 MIT LICENSE，公开脚本时保留归因。数据条款与代码许可证是两份不同文件，不能因为代码采用 MIT 就默认电影评分也可任意再分发。

**L83–L90。** 注释说明 kernel 只注册在项目里。创建 baseline/.jupyter/kernels/p1-baseline/kernel.json；argv 的第一个元素是 sys.executable，保证 notebook 使用当前 baseline 环境。-m ipykernel_launcher 启动内核，-f 后的 {connection_file} 是 Jupyter 运行时填写的连接文件占位符。display_name 是界面标签，language 用于前端识别。

**L91–L95。** JUPYTER_PATH 让子进程找到局部 kernel，PYTHONIOENCODING 统一 Python 文本编码。两个线程变量限制 BLAS/OpenMP 的调度并减少额外波动。它们在 notebook 内核启动前设置，因此能由子进程继承；没有改动原 BPR 的模型构造参数。固定线程和 seed 有助于复现，不保证所有硬件与库版本逐位相同。

### run：执行副本，保留原始目标

**L97–L103。** run 输入 sar 或 bpr 字符串，最后返回比较报告字典。nbformat 读写 notebook，NotebookClient 真正执行，HTMLExporter 生成可直接阅读的页面。原文件读两次，分别得到 original 与 nb 两个独立对象；original 用于读取原保存值，nb 用于清除旧输出和执行，磁盘原件不改写。

**L104–L110。** 创建一个新的代码单元，在 kernel 中把固定 checkout 放到 sys.path 最前面，确保 import recommenders 命中指定版本。!r 把路径变成合法 Python 字符串表示，正确保留 Windows 反斜杠。这个单元打印 commit，并在 metadata 标记它属于本地适配。insert(0, preamble) 放在所有原单元之前。

**L111–L121。** changes 记录修改说明。遍历 nb.cells[1:] 跳过刚插入的单元；只处理代码单元，清空旧 outputs 和 execution_count。这样后来看到的结果来自本次运行，不能混用原作者保存的输出。只有找到原数据加载调用时，才加 local_cache_path 参数。标签、切分、模型和 evaluator 参数均未改动；每项适配另写入 changes，便于审查。

### capture：生成一个只做审计的末尾单元

**L122–L128。** 指定本模型的 run_details.json 路径。capture 是将要交给 kernel 执行的 Python 源码字符串；它尚未在运行器进程中执行。连续的字符串字面量自动拼接。字符串里的 \n 表示新行；L128 的双层转义让生成代码中的 lineterminator 成为换行符。这一行把 DataFrame 按当前行序转 CSV 再哈希，记录的是切分内容与顺序，不是 ZIP 的摘要。

**L129–L137。** 构造 details 字典。len 得到行数，nunique 得到用户/物品数。集合交集统计训练和测试共有用户；差集统计测试独有用户。isin 找测试物品是否出现在训练中，~ 取反，sum 计数不可由训练物品目录推荐的测试记录。随后保存 train/test 哈希、处理后数据行数和原 notebook 的固定 seed。seed=42 是对已锁定原代码的描述，不是动态改写训练随机数。

**L138–L141。** 读取 notebook 真正计算出的四个 eval 变量。float 将 NumPy 标量转成普通 Python 数，保证 JSON 能序列化；不会改变排序算法。括号和字典收尾结束 capture 的基础部分。

**L142–L151。** SAR 额外保存已执行的五项 rating metrics、训练/预测计时和 top_k 行数；BPR 保存 all_predictions 行数。两个 notebook 的变量不同，所以分支按真实来源读取。rating metrics 的解释范围仍受上游真值/预测内连接影响，不能仅因为导出了数字就称为完整测试评分误差。

**L152–L153。** 把 JSON 写入语句与 print 拼到 capture 末尾，再追加为最后一个新代码单元。写文件这一步必须在 kernel 中完成，因为 train、test、eval_map 等变量只存在于 notebook 内核的运行状态。使用 !r 处理输出路径，避免手工转义错误。

### 执行、失败记录和比较

**L154–L160。** perf_counter 开始计时，output 指向 executed.ipynb。NotebookClient 为每个单元设置 1200 秒超时，指定项目 kernel 和报告工作目录。client.execute 才真正按顺序执行。finally 不论成功失败都保存当前 notebook，因此失败时也有运行到哪里、哪个单元报错的证据。若执行抛异常，后面的“成功比较”不会继续执行，不能误写成功状态。

**L161–L164。** 执行成功后转换成 HTML，写 UTF-8 文件。然后分别从本次输出和原保存输出读取 metadata。HTML 与 executed.ipynb 含原数据示例，只用于本地教学，已被 Git 忽略。

**L165–L172。** 建立比较报告：模型名、成功状态、固定 commit、源文件路径、源 notebook hash、实际总耗时，以及原代码单元数量和已执行单元数量。执行数包含前置与后置两个辅助单元，因此 SAR 是 15→17，BPR 是 11→13。适配列表明确哪些变化属于环境与证据层，避免把适配隐藏起来。

**L173–L179。** 同时保留完整精度的原值与实测值；四个指标逐个计算绝对差。all(...) 要求每一项都小于等于 10^-6。路径用于找到 notebook/HTML；important 字段提醒公开边界。这一容差只针对排序指标，不对训练耗时作一致要求。

**L180–L182。** 将本模型比较写入 JSON，在终端打印，并返回给 main。flush=True 让正在运行时的进度及时出现，而不等缓冲区满。该函数返回可检查的报告，而不是仅返回 True。

### main：统一入口与退出条件

**L184–L188。** argparse 限制 --model 为 sar、bpr、all，默认 all；输错名字会显示命令用法。解析后先执行 setup，任何来源或数据校验失败都会阻止后续训练。

**L189–L196。** 用当前解释器执行 pip freeze，保存本次实际环境；它记录当前状态，不会自动回滚错误的环境。环境准备仍应先走 setup.ps1。environment.json 记录 Python、解释器路径、平台和依赖选择理由。这样“在我的电脑能运行”能够进一步指向具体可检查版本。

**L197–L201。** all 时遍历 NOTEBOOKS 的两个键；指定单模型时只生成一个名字列表。逐个调用 run，写总摘要，再统一检查 numeric_match_at_tolerance。只要有一项未匹配，就抛 RuntimeError 返回非零；比较文件保留差异供诊断，不把失败抹掉。

**L203–L205。** __name__ 判断区分“直接运行脚本”和“被其他脚本导入”。只有直接运行才调用 main；末尾空行没有执行作用。这使我们能单独导入 setup 做来源/缓存核验，而不重复训练模型。

## B. check_bpr_math.py：把手推梯度与实际数值相对照

### 目标函数与解析梯度

**L1–L12。** 模块 docstring 给出已检查的 Cornac 2.3.0 源码 URL，并明确范围：检查一个固定用户、正物品、负物品三元组的数学更新，不声称穷尽检查编译后训练器所有路径。json 保存证据，Path 定位输出，NumPy 进行向量运算。这里不调用 Cornac 训练。

**L14–L18。** objective 输入长度 11 的浮点向量和正则系数，返回单个目标值。前 3 个数是用户向量，随后 3 个是正物品，再后 3 个是负物品，最后两个是各自偏置。@ 是内积；gap 为用户对正负物品的分数差。−logaddexp(0,−gap) 等于 log sigmoid(gap)，能避免先算指数再取对数产生部分数值溢出。theta @ theta 是全部参数平方和，乘 0.5λ 后扣除，规定采用最大化目标的符号。

**L20–L25。** analytic_gradient 使用同一套分块与分数差。z=1/(1+exp(gap)) 等于 sigmoid(−gap)，也是 log sigmoid(gap) 的导数。L24 的 np.r_ 按原参数顺序拼接五块：用户的 z(q_i−q_j)、正物品的 zp、负物品的 −zp、正偏置的 z、负偏置的 −z。L25 对每个参数减去 λθ，得到完整梯度。这个小核验固定输入在普通数值范围；L23 没有宣称适用于任意极端 gap 的通用稳定 sigmoid 实现。

### 中心有限差分逐参数检查

**L27–L30。** main 选取非零、有正有负的 11 个固定参数，避免全零例子掩盖符号问题。float64 提供差分所需的精度。regularization=0.1、epsilon=10^-6、learning_rate=0.01 是核验例子的数值，不是原 notebook 的训练超参数；两者不要混淆。

**L31–L37。** analytical 保存手推公式结果，numerical 初始化相同形状的零向量。循环一次检查一个坐标；plus 与 minus 都复制原 theta，不能在原数组上累计扰动。分别对同一个坐标加、减 epsilon，再用两个目标值之差除以 2epsilon。这就是中心差分，相比只往一个方向扰动更能抵消一阶截断误差。

**L38–L43。** error 是每个坐标差值取绝对值后的最大数，能发现某一个偏置或向量分量写错而平均值掩盖的问题。before/after 检查本例沿正确梯度迈一小步后目标是否增加。三个 norm 值分别是原参数范数、只做负正则收缩后的范数、错误地用正号放大后的范数。这里暂时隔离似然项，专门检验正则方向。

**L44–L46。** 三个 assert 分别要求最大误差 <10^-7、目标上升、范数收缩方向正确。实际最大误差约 1.095×10^-10；目标从 −0.7551046480 增至 −0.7463151328；正确正则使范数从 0.8560957890 降至 0.8552396932。assert 是实验检查，正常命令不加 Python -O；-O 会关闭断言，因此不应以优化模式执行验收脚本。

### 证据输出与解释边界

**L47–L54。** result 保留 PASS、目标约定、完整输入参数、差分步长、两组 11 维梯度、最大误差、目标变化和范数变化。NumPy 数组用 tolist 转成 JSON 列表。另存 x=1 时的导数 0.2689414214，便于直接检查正负号；该值应为正。

**L55–L58。** 保存实际检查过的源代码位置与结论。结论区分“原 notebook 展示公式错误”和“Cornac 实现更新正确”；scope 再说明只核验一个三元组，避免把有限差分通过夸大成全部实现正确的证明。

**L59–L62。** 从脚本位置找到项目 reports/baseline，必要时创建父目录，以 UTF-8 输出 bpr_gradient_check.json 并打印同一份结果。输出 JSON 足够别人重算这个小例子，无需访问任何真实用户评分。

**L64–L65。** 直接运行时进入 main，被导入时只定义函数。这使 objective 与 analytic_gradient 可以被其他小型测试复用。

## C. 本节代码的学习检查

手工改变 theta 的最后一项，解释它为什么影响 gap 的方向与正偏置相反；删去解析梯度的一个负号，观察哪一维误差先变大；比较只校验 ZIP 与同时校验解压文件的差别；解释为什么 finally 保存 notebook 仍不能把一次失败运行算成功。练习请另存副本，不覆盖已验收报告。

## D. 源码指纹

| 文件 | 行数 | SHA-256 |
|---|---:|---|
| baseline/run_upstream.py | 205 | 71c8feb0c3cf651f80e19897ab6f3e9436f795dc2b2e565549a64bfd1610d4d5 |
| baseline/check_bpr_math.py | 65 | 1ceb604c034a90dbb71e3bf364f1eb7046699f45f6cb93f2fa129031c4883f45 |

如果源码 hash 变化，应先更新行号与解释，再重建伴册。已保存指标不因修改文档自动变成新实验结果。

## E. setup.ps1：环境准备脚本逐行解释

**L1–L4。** param 声明两个可覆盖的字符串参数：Workspace 控制外部源码、数据和缓存所在目录，Python 指向用来创建环境的 Python 3.12。默认值对应本机已经核验的位置；换电脑时通过命令参数提供实际路径。声明类型 [string] 便于 PowerShell 做输入转换，括号收尾属于参数块。

**L5–L8。** ErrorActionPreference='Stop' 让 PowerShell cmdlet 遇到错误时停止。它不能保证所有原生 exe 的错误都会变成异常，所以后面还检查 LASTEXITCODE。Commit 固定上游版本；Join-Path 用目录与子路径组合目标。PSScriptRoot 是当前 setup.ps1 所在目录，所以 EnvPython 始终是这份 baseline/.venv 的解释器，不会指向主项目 .venv。

**L9–L12。** 给 uv 和 pip 都设置 H 盘缓存路径，避免依赖下载占用系统盘。P1_WORKSPACE 传给 Python 复现器，PYTHONIOENCODING 统一终端编码。这些值是当前会话/子进程环境，不是删除或迁移系统目录，也不是更改操作系统全局 HOME。

**L13–L16。** 只在 SourcePath 不存在时克隆仓库。Test-Path 的 LiteralPath 按字面路径处理，不把字符当通配符。New-Item -Force 准备父目录，Out-Null 仅隐藏对象输出。Git 的 --filter=blob:none 按需取得文件对象，--no-checkout 暂不铺开工作文件；其后必须选择所需目录并 checkout。克隆失败时立即 throw，防止继续执行一个不完整源码树。

**L17–L23。** sparse-checkout init --cone 启用目录式稀疏检出；set 指定 recommenders 包和两个示例目录；checkout 最后定位固定 commit。每个 Git 步骤都检查 LASTEXITCODE。稀疏检出减少本地不相关文件，并不删除上游仓库内容。这个代码块只在刚创建本实验源码目录时执行，不会强制重置用户已有的其他版本。

**L24–L27。** 对新建或已有源码都读取 HEAD，再检查 Git 成功且提交一致。不同版本时提示保留原目录并选择独立工作区；不会自动硬重置或清除修改。这里验证提交编号，运行器还会在正式执行前验证相关源码 Git diff。

**L28–L33。** 环境解释器不存在时才使用指定 Python 执行 -m venv。创建失败就停止。随后实际运行 EnvPython，检查 sys.version_info 的前两项恰为 (3,12)，不只相信文件夹名字。此命令不带 -O，所以 assert 会执行。版本不符会明确报错，保留原环境。

**L34–L39。** 如果 Get-Command 找得到 uv，就用 uv pip install --python 指定目标环境；否则使用该环境自身的 python -m pip。两个分支都读取同一份 baseline/requirements-lock.txt，并在结束后检查退出码。SilentlyContinue 仅用于“是否安装 uv”的探测，不用于忽略真正安装失败。-r 指读取依赖清单，不是运行 Python 文件。

**L40–L43。** pip check 校验已安装包的依赖声明是否互相满足；它不执行模型，也不证明数值结果。检查成功才打印 Ready 与 Pinned source。接着还必须执行 run_upstream.py 完成真实 notebook 验收，不能把环境安装成功当成项目已复现。

## F. 配置与锁定依赖怎样配合

本基线的“配置”分为三处：setup.ps1 的 Workspace/Python 决定机器路径；run_upstream.py 的 COMMIT、NOTEBOOKS、固定数据 SHA 和 --model 决定重现对象；真正的模型和切分参数仍在锁定的原 notebook 中。不能修改原 notebook 的因子数，然后继续声称同一份原样结果已复现。修改参数应另开实验版本。

baseline/requirements-lock.txt 共 76 行，每一行的“包名==精确版本”都进入安装约束。其行号说明如下；这里按用途分组，完整清单保留在 HTML 源码区，不要求把每个传递依赖背下来。

| 关键行 | 作用 |
|---|---|
| L11 Cornac 2.3.0 | 执行实际 BPR 训练器；选择它是为满足 NumPy/SciPy 兼容约束 |
| L40 NumPy、L42 pandas、L60 scikit-learn、L61 SciPy | 数组、评分表、切分/工具和稀疏计算；版本变化可能影响数据类型或数值路径 |
| L19–L20、L27–L28、L36–L38 | kernel、交互环境、Jupyter通信，以及 notebook 执行、导出和格式读取 |
| L32–L33、L62 | notebook 绘图和可视化依赖，不构成新推荐算法 |
| L57–L58、L69、L71、L74 | HTTP、重试、进度、操作系统证书库和 HTTP 底层库 |
| 其余精确版本行 | 上述包的导出、模板、文字编码、类型、线程、日期、调试与格式校验依赖，保持完整环境可重建 |

pip freeze 保存的是当时实际安装的所有包，通常比直接依赖列表长。不要把未单独 import 的间接依赖误删；先让安装工具解析、再运行 pip check，最后真正执行 notebook，三个阶段的证据分别保留。跨平台重建若某个锁定 wheel 不可用，需要记录新的兼容环境并重新验证指标，不能直接沿用 Windows 结果作为新平台已经通过的证据。

| 补充文件 | 行数 | SHA-256 |
|---|---:|---|
| baseline/setup.ps1 | 43 | 7cda13b9026c813c8f10cfe9d0302135565430c2cb05307f907567b7acae1b44 |
| baseline/requirements-lock.txt | 76 | 58cb19f7837a65bc3a9233fc55b7b567e1c1333e54663d74fe0543a8a6fc0359 |
