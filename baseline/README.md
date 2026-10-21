# 原版 SAR / BPR 复现实验

这里运行 Recommenders 仓库固定提交的两个完整 notebook。提交是 `aa8332189cd495be6ffaa7e1c8054f1c180b5ef3`；原文件留在 `H:\Career_AI_Portfolio\external\recommenders`，没有改写算法。两项实验在 MovieLens 100K 上完成，八项排序指标均与各自原 notebook 保存值一致。完整证据见 `../reports/baseline/reproduction_report.md`。

## 重跑

在项目根目录打开 PowerShell，执行：

```powershell
& .\baseline\setup.ps1
& .\baseline\.venv\Scripts\python.exe .\baseline\run_upstream.py
& .\baseline\.venv\Scripts\python.exe .\baseline\check_bpr_math.py
```

第一条准备 Python 3.12 环境、固定源码与锁定依赖，并运行 `pip check`。第二条逐单元执行原 notebook，导出 HTML、JSON 和数据校验值；第三条用有限差分核对 BPR 梯度。命令出错会返回非零退出码，不会把失败算作完成。只运行一个模型时，在第二条后追加 `--model sar` 或 `--model bpr`。

默认工作区为 `H:\Career_AI_Portfolio`。如果目录或 Python 安装位置不同，明确传入：

```powershell
& .\baseline\setup.ps1 -Workspace 'X:\Career_AI_Portfolio' -Python 'X:\Python312\python.exe'
$env:P1_WORKSPACE = 'X:\Career_AI_Portfolio'
& .\baseline\.venv\Scripts\python.exe .\baseline\run_upstream.py
```

`P1_WORKSPACE` 控制外部源码、数据和缓存所在位置。当前项目目录由脚本自身位置确定。`setup.ps1` 不会覆盖不同版本的现有源码目录；遇到这种情况请给本实验单独的工作区。

## 文件与输出

| 文件 | 用途 |
|---|---|
| `setup.ps1` | 创建隔离环境、固定源码、安装锁定依赖 |
| `requirements-lock.txt` | 本次实际环境的完整版本记录 |
| `run_upstream.py` | 完整 notebook 执行与证据导出 |
| `check_bpr_math.py` | 正则化符号与梯度的有限差分检验 |
| `UPSTREAM_LICENSE` | Recommenders 的 MIT 原许可证 |
| `../reports/baseline/*_comparison.json` | 固定来源、原值、实测值、误差、修改范围 |
| `../reports/baseline/*_run_details.json` | 数据量、切分哈希、用户数量与实测指标 |
| `../reports/baseline/*_executed.ipynb` / `.html` | 完整执行记录，含原数据示例，只留本地 |
| `../reports/baseline/bpr_gradient_check.json` | 数学检查的输入、输出和误差 |

本地 archive 是 `H:\Career_AI_Portfolio\data\movielens\ml-100k.zip`，SHA-256 为 `50d2a982c66986937beb9ffb3aa76efe955bf3d5c6b761f4e3a7cd717c6a3229`。下载走 GroupLens 官方 HTTPS；使用操作系统证书库，保留 TLS 校验。原始数据、含数据示例的 notebook/HTML、虚拟环境和缓存均不放入公开 Git。

## 我们改了什么

执行副本只增加固定源码导入路径、本地数据缓存路径和末尾证据导出单元。原 notebook 的标签、切分、模型、评估参数与所有原始代码单元均保留。SAR 执行原始 15 个代码单元，BPR 执行原始 11 个；各另加 2 个辅助单元。

本次固定 NumPy 1.26.4、SciPy 1.13.1、pandas 2.2.3、scikit-learn 1.5.2、Cornac 2.3.0。Cornac 2.3.5 要求 NumPy > 2，与此固定 Recommenders 源码声明的 NumPy < 2 冲突。保守版本组合已经实际执行通过，完整间接依赖见 lock 文件。没有安装与这两个 notebook 无关的 Spark、TensorFlow、GPU extras。

## 结论的范围

SAR 和 BPR 使用不同的正反馈与切分方式，所以本目录的两列指标不能用于模型优劣比较。项目自己的 MovieLens 1M 时间切分、公平评估和重排扩展在 `src/reclab` 与 `reports/experiment`，有独立协议。

这些结果证明本次环境中的完整复现，不代表我们发明了 SAR/BPR，也不代表线上用户收益。BPR 原 notebook 展示公式存在符号问题；Cornac 2.3.0 实际更新式使用正确的负正则项。我们保留原文件，并在教学与数学检查中解释差别。

- [SAR 固定源码](https://github.com/recommenders-team/recommenders/blob/aa8332189cd495be6ffaa7e1c8054f1c180b5ef3/examples/00_quick_start/sar_movielens.ipynb)
- [BPR 固定源码](https://github.com/recommenders-team/recommenders/blob/aa8332189cd495be6ffaa7e1c8054f1c180b5ef3/examples/02_model_collaborative_filtering/cornac_bpr_deep_dive.ipynb)
- [MovieLens 官方数据目录](https://grouplens.org/datasets/movielens/100k/)
- [Cornac 2.3.0 BPR 更新代码](https://github.com/PreferredAI/cornac/blob/v2.3.0/cornac/models/bpr/recom_bpr.pyx#L247-L266)
