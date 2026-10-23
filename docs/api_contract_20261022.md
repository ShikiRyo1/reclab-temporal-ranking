# 0.1.2接口类型修复与核验

本次修复从实际请求中发现：旧接口会把 `{"k":true}` 变成 `k=1`，把 `"1161"` 变成整数用户ID。数值范围没有越界，但调用方传错类型的事实被掩盖了。修复集中在API输入层，训练、重排逻辑和模型文件没有改动。

## 请求现在怎样处理

| 字段 | 接受 | 返回422 |
|---|---|---|
| `user_id` | 大于等于1的JSON整数；`null`表示冷用户 | `true`、`"1161"`、`1161.0`及越界数值 |
| `k` | 1至50的JSON整数 | `true`、`"10"`、`10.0`及越界数值 |
| `novelty_weight` | 0至1的有限JSON数值，包括整数0、1；或`null` | 布尔值、字符串数字、非有限数值、越界数值 |

`src/reclab/api.py`第32、33行给整数字段加 `strict=True`，在Pydantic解析请求时就拒绝错误类型。第35行同样启用严格检查，并用 `allow_inf_nan=False` 拒绝非有限权重。在当前Pydantic 2.14.1中，严格浮点字段仍接受整数0和1，这符合权重作为数值的定义；它不会接受Python中可充当整数的布尔值。

`null`沿用原有默认行为：暖用户使用模型选定的0.2；冷用户走热门推荐，实际生效权重为0。请求权重与生效权重在响应中分开报告。整数或浮点权重都不改变这一逻辑。

## 代码和测试怎样对应

`tests/test_api.py`第141—149行覆盖11种错误类型，检查HTTP 422以及报错字段位置。第152—160行覆盖0、1、0.2和`None`，同时确认仍返回个性化策略、正确条数与权重。单元测试使用合成artifact，其默认权重为0；真实部署模型的默认权重为0.2，两者不能混为一谈。

本机最终运行得到65项测试通过，另有1条既有Starlette/httpx弃用警告。实际Docker服务完成17项原有HTTP检查，以及15项新增类型/合法权重请求。`reports/release/verify_api_contract_20261022.py`保存了这15个HTTP案例和版本、模型hash、本机依赖检查；它不训练模型，也不保存逐用户推荐列表。

在项目根目录重查：

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/verify_live.py --output reports/release/recheck_http.json
.venv/Scripts/python.exe reports/release/verify_api_contract_20261022.py
```

最后一条默认生成带UTC时间戳的新JSON；也可以用 `--output` 指定尚不存在的文件。脚本拒绝覆盖旧证据，开始时先写 `RUNNING`，正常结束写 `PASS` 或 `FAILED`，遇到HTTP、解析或容器异常也写 `FAILED`。如果进程被强制终止，留下的 `RUNNING` 表示未完成，不应当作通过。原始验收日志和冻结实验不受影响。

## 版本、构建与结论边界

包常量、安装元数据、FastAPI和Compose镜像标签均为0.1.2。实际运行的模型仍为 `ml1m-bpr-506d64ca-30794fbd-w0.2`，SHA-256为 `14874e07e00af8f4d9b4e94f51ebb0b368a6fdc5b98391697a4f6c846fb8b5ad`。0.1.0旧镜像保留在本机。

最终构建复用了已安装API依赖的Docker层；重新构建了本项目wheel。构建日志显示安装了隔离构建依赖，但没有给出其精确版本或网络下载字节数，因此这两项记为未知。基础镜像的digest保持固定。`setuptools>=75`是构建条件，尚未精确锁定；不能据此声称镜像可逐字节重建。开始/结束UTC、base digest、新旧image ID及原始输出见 `reports/release/reaudit_20261022_docker_build_final.json` 和同名本地log。

这一轮重新核对了两份上游notebook的历史执行结果、源代码hash及8项排序指标，没有重新运行notebook或训练模型。冻结模型的时间切分与指标计算已独立复核，但仍只有一个时间窗口和训练seed。此前0.1.0的500请求压测只保留为历史证据，不能当成本次0.1.2的性能测量。
