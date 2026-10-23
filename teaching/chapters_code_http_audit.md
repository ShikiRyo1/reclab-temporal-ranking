# 2026-10-22真实HTTP验收脚本电子伴读

本节只加在电子索引中，供需要重跑审计时查阅。37页Word伴读已讲服务、原测试与Swagger回放；这里补充独立验收脚本，不把同一段长代码再印一遍。

## reports/release/verify_api_contract_20261022.py

**L1–L14。** docstring限定为0.1.2的真实HTTP契约检查，不训练模型。datetime/timezone记录UTC；argparse解析输出位置；hashlib检查模型字节；importlib.metadata读取已安装发行包版本；json/Path处理报告；subprocess调用容器与pip；sys选择当前解释器和退出码。httpx发真实请求，reclab提供包内版本。ROOT从脚本位置回退两层，不依赖启动终端目录。

**L15–L21。** verify接受报告路径，初始化开始时间和检查列表；invalid列出11种非法类型。这里Python的True、False会被HTTP客户端序列化为JSON的true、false；它们不是字符串，也不能被整数参数默默接受。

**L22–L29。** 建立指向8011的真实客户端，超时30秒；逐个POST后，取输入字段名并核对422与detail中对应的body字段。把请求、状态和真假写入列表。错误JSON或缺少detail也会让外层失败，不能因HTTP本身成功就计通过。这是本机服务检查，不是离线TestClient。

**L30–L39。** 4个合法权重分别为0、1、0.2和None。暖用户1161应返回10项个性化结果，并正确记录请求/实际权重；None在真实冻结模型中得到0.2。它和微型测试fixture默认0不同。这里只保存参数与检查结果，不复制逐项推荐列表。

**L40–L46。** 读取OpenAPI版本和ready；对本地model.joblib算SHA，并要求本地值、在线值、原发布固定值三者相同。模型版本字符串也与原值对照。这说明本轮修API而模型未换，不证明模型预测质量提高。

**L47–L57。** version_code是要在容器内执行的一段Python字符串，读取包的__version__与安装发行版版本。docker compose exec -T禁用伪终端；参数列表避免shell插值，cwd固定项目，check=True使失败抛错。随后核对容器、本地包/发行版及OpenAPI全部为0.1.2。代码发布版本与模型版本是两层身份。

**L58–L68。** 逐行读取requirements-lock.txt，对每条包名==版本检查当前已装发行包。计数只加实际版本行，注释不参与。收集全部不匹配，不只挑第一项；记录的50是当前完整开发锁的条数，不是Docker服务镜像包数。

**L69–L72。** 用sys.executable执行当前环境的pip check，保留退出码、stdout和stderr。这检查依赖声明兼容，不保证所有路径没有bug，也不会替你升级包。

**L73–L83。** 通过条件要求15项HTTP、原模型身份、代码版本、依赖版本及pip check同时满足。记录结束UTC、执行范围和PASS/FAILED后写JSON，控制台输出位置/状态/检查数，退出0或1。scope明确没有重训、重新执行Notebook或重新压测。

**L86–L95。** 命令入口接受--output；省略时创建带UTC微秒的文件名。指定相对路径时，resolve按当前工作目录解析，因此下面命令要求先进入P1根目录。建立父目录并准备passed=false的RUNNING标记。

**L96–L98。** open模式x要求新文件独占创建；路径已存在就拒绝，保护原验收结果，也防止两个检查复用同一输出名。先写RUNNING，使正在运行的文件不能被当成PASS。

**L99–L107。** 调用verify；遇到HTTP、JSON、容器等异常时，写FAILED、异常类型与说明，stderr打印失败概况并退出1。没有声称能保证磁盘写入故障后的恢复；程序硬中断也可能只留下RUNNING。两者都不能计为通过。

**L110–L111。** __name__守卫使import不自动发请求；直接运行时SystemExit把main返回值传给终端。

已执行证据见reports/release/reaudit_20261022_postfix_contract.json和本轮审计报告。学习时先进入P1根目录，然后运行 `./.venv/Scripts/python.exe reports/release/verify_api_contract_20261022.py`，会新建带时间戳的报告；想指定位置可加 `--output reports/learner/api_contract.json`，但已有该文件时须换一个新名字。默认时间戳方式适合重复练习。

练习：类型错误应422，为什么仍要测合法0与1？因为“拒绝所有输入”也能通过单边拒绝测试。再问：程序失败但磁盘有旧PASS能算通过吗？不能，要看本次开始时间、状态和退出码；本脚本拒绝复用旧文件正是为避免这种混淆。
