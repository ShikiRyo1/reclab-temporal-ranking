# 上游完整复现记录

## 验收结果与目标

从固定 Recommenders 源码完整执行 SAR quick start 和 Cornac BPR deep dive，所有原代码单元执行成功：SAR 15/15、BPR 11/11，每本额外加入两个辅助单元。八项排序指标与对应原 notebook 保存值逐项精确一致，绝对误差均为 0，满足预设容差 \(10^{-6}\)。

复现目标是两个 notebook 各自的协议。没有把 README 汇总表作为替代目标，也没有用项目后来统一的时间协议改写原样结果。

| 项目 | 固定值 |
|---|---|
| 仓库 | https://github.com/recommenders-team/recommenders |
| 提交 | `aa8332189cd495be6ffaa7e1c8054f1c180b5ef3` |
| 原源码许可 | MIT；副本 `baseline/UPSTREAM_LICENSE` |
| SAR 文件 | `examples/00_quick_start/sar_movielens.ipynb` |
| BPR 文件 | `examples/02_model_collaborative_filtering/cornac_bpr_deep_dive.ipynb` |
| 数据 | GroupLens MovieLens 100K，原始评分 100,000 条 |
| ZIP 字节数 | 4,924,029 |
| ZIP SHA-256 | `50d2a982c66986937beb9ffb3aa76efe955bf3d5c6b761f4e3a7cd717c6a3229` |
| SAR notebook SHA-256 | `ec93b1fb81864b7ae9ce22a7ba46b53947f2c3cfe5fce982c31c4b7594569547` |
| BPR notebook SHA-256 | `354f97cf72d8a7d4c110fc024206a9f14c0a79a5c41e9531bd4a2f3f51c09abc` |

运行器检查源码 HEAD、相关源码的 Git diff、数据 ZIP 哈希和 ZIP 完整性，并核对实际读取的 u.data、u.item 与 ZIP 内原件逐字节相同。源码版本或数据字节不符时停止。分割哈希算法是对原训练/测试 DataFrame 按原行序执行 `to_csv(index=False, lineterminator='\n')`，UTF-8 编码后计算 SHA-256；不是压缩包哈希。

## 实际环境与命令

Python 3.12.4 / Windows；NumPy 1.26.4、SciPy 1.13.1、pandas 2.2.3、scikit-learn 1.5.2、Cornac 2.3.0。完整版本在 `baseline/requirements-lock.txt`，环境信息在 `environment.json`。环境位于 `baseline/.venv`，缓存位于 H 盘。`setup.ps1` 复核了 76 个包，`pip check` 输出 `No broken requirements found.`。

最终核验使用以下 PowerShell 命令。实际日志和 notebook 输出已经保存：

```powershell
& 'H:/Career_AI_Portfolio/projects/01_recommendation_service/baseline/setup.ps1' *> 'H:/Career_AI_Portfolio/projects/01_recommendation_service/reports/baseline/setup.log'
$env:PYTHONIOENCODING='utf-8'
& 'H:/Career_AI_Portfolio/projects/01_recommendation_service/baseline/.venv/Scripts/python.exe' 'H:/Career_AI_Portfolio/projects/01_recommendation_service/baseline/run_upstream.py' *> 'H:/Career_AI_Portfolio/projects/01_recommendation_service/reports/baseline/execution.log'
& 'H:/Career_AI_Portfolio/projects/01_recommendation_service/baseline/.venv/Scripts/python.exe' 'H:/Career_AI_Portfolio/projects/01_recommendation_service/baseline/check_bpr_math.py'
```

依赖修复：Cornac 2.3.5 要求 NumPy > 2，但固定 Recommenders 声明 NumPy < 2；Cornac 2.3.0 又要求 SciPy ≤ 1.13.1。因此选用上述兼容组合，完整重跑。下载最初遇到本机证书链问题，改用 `truststore` 读取操作系统证书库，没有关闭 HTTPS 证书检查。

上游源码直接从固定 checkout 导入，不安装所有可选组件。Notebook 通过 `nbclient` 在项目局部 kernel 中执行，再用 `nbconvert` 导出 HTML，没有全局安装 kernel。`OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1` 控制 CPU 调度，原模型构造参数不变。

## 两个原协议

| 细节 | SAR 原 notebook | BPR 原 notebook |
|---|---|---|
| 输入 | 100,000 条评分及时间戳；rating 转 float32 | 评分严格大于 3.5 后转 1，保留 55,375 条正反馈 |
| 切分 | 每用户分层随机 75/25，seed 42 | 全局随机 75/25，seed 42 |
| 训练/测试行数 | 74,992 / 25,008 | 41,531 / 13,844 |
| 训练/测试用户数 | 943 / 943 | 942 / 930 |
| 训练/测试物品数 | 1,653 / 1,444 | 1,395 / 1,160 |
| 模型参数 | Jaccard；30 天半衰期；启用时间衰减、评分归一化 | 200 factors；200 epochs；lr 0.01；lambda 0.001；seed 42 |
| 已见物品 | 排除训练已见物品 | 排除训练已见物品 |
| 候选评分 | 测试用户推荐前 10，共 9,430 行 | 默认 `top_k=None`，生成全部未见候选，共 1,272,559 行，再由 evaluator 取前 10 |
| relevant 定义 | 测试集中的所有评分记录 | 测试集中的高分正反馈 |

原 evaluator 仅对预测和测试都出现的用户计算排序指标：本次 SAR 为 943、BPR 为 930，均没有测试独有用户。训练中没有的物品仍可能保留在测试 relevant 数量中：SAR 有 35 条此类测试记录，BPR 有 63 条。本次保留原行为，额外输出这些数量，见 `*_run_details.json`。独立时间评估另外明确候选资格和分母。

SAR 的 30 天参数是半衰期：距离训练数据最新时间 30 天的交互权重减半。`normalize=True` 对预测按原评分尺度做归一化，不等于概率校准。BPR 推荐分数包含用户/物品向量内积和物品偏置，分数也不等于购买概率。

| 切分 | SHA-256 |
|---|---|
| SAR train | `65f080ee1622582892ff64229906dccc0c015bd7930b30a8269f8c0e08f0e8a9` |
| SAR test | `95359558742cb7c2b4a3a500f6b5764b77e93493c4cd5ab9ed197c2bd6f8e3d6` |
| BPR train | `cdd627c990a1dad7e2e0e916e07b3dddfe6f892e81f1d1abeada648e0119997b` |
| BPR test | `95b92ee66b84dc76d6fea9bf019ca27f4ba5fe7c50bec2363d59b3ba2711af21` |

## 实测与预期对照

| 实验 | 指标 | 上游保存值 | 本次实测值 | 绝对误差 |
|---|---|---:|---:|---:|
| SAR | MAP@10 | 0.24472205306261383 | 0.24472205306261383 | 0 |
| SAR | NDCG@10 | 0.3795334514937595 | 0.3795334514937595 | 0 |
| SAR | Precision@10 | 0.3310710498409332 | 0.3310710498409332 | 0 |
| SAR | Recall@10 | 0.17683684715427114 | 0.17683684715427114 | 0 |
| BPR | MAP@10 | 0.180367644269974 | 0.180367644269974 | 0 |
| BPR | NDCG@10 | 0.3051899536864835 | 0.3051899536864835 | 0 |
| BPR | Precision@10 | 0.23903225806451614 | 0.23903225806451614 | 0 |
| BPR | Recall@10 | 0.20866044380376064 | 0.20866044380376064 | 0 |

运行耗时随机器和负载改变，不要求与原 notebook 一致，不作跨机器加速声明。每次实际耗时由 `*_comparison.json` 和 notebook 保存。

SAR notebook 的 rating metrics 也完整运行：RMSE 1.2292462563753148、MAE 1.0339118567019978、R² −0.5113335264543022、explained variance 0.0984935612370964、log loss 0.5691526604461454。真值与预测通过用户/物品内连接，只覆盖进入推荐结果且与测试匹配的记录；不能把它们解释成对全部测试评分的回归评价。本项目不使用这些数值证明评分预测能力。

原 README 汇总表另列 SAR NDCG 0.3938，而固定 notebook 保存的是 0.3795334514937595。我们验证后者。仅凭汇总表无法确认同一环境和协议，也没有证据把差异归因于某一个包版本。本次结果不能改写成匹配所有上游摘要表。

## BPR 公式核验

设用户向量为 \(p_u\)，正、负候选向量为 \(q_i,q_j\)，偏置为 \(b_i,b_j\)：

\[
x=p_u^\top(q_i-q_j)+b_i-b_j,\qquad
J=\log\sigma(x)-\frac{\lambda}{2}\|\Theta\|_2^2.
\]

采用最大化 \(J\) 的梯度上升，有

\[
\frac{d\log\sigma(x)}{dx}=1-\sigma(x)=\sigma(-x)>0,\qquad
\nabla_\Theta J=\sigma(-x)\nabla_\Theta x-\lambda\Theta.
\]

如果最小化负对数似然 \(L=-J\)，梯度整体反号，再用梯度下降，参数变化一致。如果正则写作 \(-\lambda\|\Theta\|^2\)，导数是 \(-2\lambda\Theta\)；这是系数约定，不能变成正的放大项。

固定 notebook Markdown 的似然导数前写了负号、梯度上升更新式中正则项写了加号。这两处展示公式需要修订。但 Cornac 2.3.0 的 `recom_bpr.pyx` 第 247–266 行使用 \(z=1/(1+e^x)\)，向量和偏置更新均减去 `reg * parameter`，与正确公式一致。本次不修改原文件，也没有证据说实际 Cornac 训练实现有这两处错误。

`check_bpr_math.py` 对 11 个固定参数做中心有限差分，步长 \(10^{-6}\)。最大绝对误差 \(1.095174784193631\times10^{-10}\)，小于 \(10^{-7}\) 门槛。一次学习率 0.01 的上升更新使目标从 −0.7551046480 增至 −0.7463151328；单独负正则更新使参数范数从 0.8560957890 降至 0.8552396932，错误的加号则升至 0.8569518848。\(x=1\) 的似然导数为正数 0.2689414214。完整参数、解析梯度、差分梯度见 `bpr_gradient_check.json`。

这个检查验证固定三元组的公式与方向，并结合源代码审阅确认实现形式；不是对所有编译后 Cornac 分支的穷尽证明。

## 归因与文件边界

SAR、BPR、原 notebook、Recommenders evaluator 与 Cornac 训练器属于原作者。我们的贡献是固定版本、兼容环境、自动完整执行、数据/切分校验、结果对照和公式核验；后续时间协议、长尾重排、服务与部署另行归因。

公开代码仓库保留脚本、许可证、环境锁、汇总 JSON 和说明。原 MovieLens 数据以及包含原始样例行的执行 notebook/HTML 只存本地，已由 `.gitignore` 排除。官方说明另存本地 `MovieLens_100K_TERMS.txt`。本阶段没有云费用，没有上传原数据，没有声称线上效果或上游已接受贡献。

可准确表达：“Reproduced the pinned SAR and BPR notebooks on MovieLens 100K, matching eight saved ranking metrics; audited protocol differences and verified the BPR gradient numerically.” 不应写成“改进 BPR 算法并超越 Microsoft”，也不能拿两列原指标直接判断模型优劣。

## 原始来源

- [SAR notebook：固定提交](https://github.com/recommenders-team/recommenders/blob/aa8332189cd495be6ffaa7e1c8054f1c180b5ef3/examples/00_quick_start/sar_movielens.ipynb)
- [BPR notebook：固定提交](https://github.com/recommenders-team/recommenders/blob/aa8332189cd495be6ffaa7e1c8054f1c180b5ef3/examples/02_model_collaborative_filtering/cornac_bpr_deep_dive.ipynb)
- [Recommenders README：固定提交](https://github.com/recommenders-team/recommenders/blob/aa8332189cd495be6ffaa7e1c8054f1c180b5ef3/README.md)
- [Cornac 2.3.0 训练更新代码](https://github.com/PreferredAI/cornac/blob/v2.3.0/cornac/models/bpr/recom_bpr.pyx#L247-L266)
- [MovieLens 100K 官方目录及说明](https://grouplens.org/datasets/movielens/100k/)
