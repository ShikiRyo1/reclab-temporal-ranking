# 上游 Notebook 逐行伴读

## 固定源码复现：从每一行到可核查的结果

本部分补齐官方 SAR 与 BPR Notebook 的所有可执行代码，不要求你一次背完。读完后应能指出每个输入从哪里来、模型在哪一行训练、哪个量只用于显示，以及为什么两个原版结果不能直接比较。先按 SAR 从读表走到评价，再用 BPR 对照切分和标签的差别。环境安装与 Notebook 的启动步骤放在本补充手册前半部。

来源固定为 Recommenders 提交 aa8332189cd495be6ffaa7e1c8054f1c180b5ef3，许可证为 MIT，版权归 Recommenders contributors。原代码保持原样；中文说明和复现辅助单元由本项目补充。完整许可证位于 baseline/UPSTREAM_LICENSE，也复制到 teaching/notebook_sources/UPSTREAM_LICENSE。未刊载 MovieLens 原始行、逐用户评分或推荐输出。

原单元和执行单元都从 1 开始计数，Markdown 单元也计入；它们与左侧 In [数字] 的执行次序不同。L1 表示该代码单元内部第一行。执行本在最前加了一个辅助单元，所以原单元 c 对应执行单元 c+1。只有两个读表单元额外插入缓存参数，后续行号因此再加 1。

原源码本地根目录为 H:\Career_AI_Portfolio\external\recommenders；SAR 文件为 examples/00_quick_start/sar_movielens.ipynb，BPR 文件为 examples/02_model_collaborative_filtering/cornac_bpr_deep_dive.ipynb。已运行副本在项目 reports/baseline/sar_executed.ipynb 与 bpr_executed.ipynb。HTML 逐行表附原文件 JSON 实体行、单元行、执行本行；完整 SHA-256 与覆盖清单在 teaching/notebook_sources/source_manifest.json。屏幕自动折行不会改变 L 编号。

阅读用源代码导出到 teaching/notebook_sources/*_code.txt，带单元边界但不含执行输出。含百分号魔法命令的片段应在 Notebook 运行，不能直接当普通 Python 文件执行。需要重跑时使用 baseline/run_upstream.py，它会刷新原执行报告；本次补充教案没有重训练或覆盖冻结结果。


### SAR 原单元 4：导入依赖与确认版本

原单元 4 → 执行单元 5；L1–L30；单元源码 SHA-256 前 12 位 e9f763b32671。

先导入后续每个单元要调用的对象。本单元只准备环境，不读取评分，也不训练模型。

代码 L1–L15（同一单元的连续片段）：

```python
import sys
import logging
import numpy as np
import pandas as pd
from sklearn.preprocessing import minmax_scale

from recommenders.utils.timer import Timer
from recommenders.datasets import movielens
from recommenders.utils.python_utils import binarize
from recommenders.datasets.python_splitters import python_stratified_split
from recommenders.models.sar import SAR
from recommenders.evaluation.python_evaluation import (
    map_at_k,
    ndcg_at_k,
    precision_at_k,
```

代码 L16–L30（同一单元的连续片段）：

```python
    recall_at_k,
    rmse,
    mae,
    logloss,
    rsquared,
    exp_var
)
from recommenders.utils.notebook_utils import store_metadata

%load_ext autoreload
%autoreload 2

print(f"System version: {sys.version}")
print(f"NumPy version: {np.__version__}")
print(f"Pandas version: {pd.__version__}")
```

L1：sys 提供 Python 解释器信息；末尾用 sys.version 确认实际内核。

L2：logging 控制训练日志的级别和格式，方便发现加载或计算异常。

L3–L4：L3 把 NumPy 命名为 np，后面用 float32 控制数值类型；L4 把 pandas 命名为 pd，后面构建用户表并合并结果。

L5：minmax_scale 用于后面的 logloss 演示，把整列预测分数缩放到 [0,1]；它不等于概率校准。

L7：Timer 是上下文计时器；with 块结束后可从 interval 读取秒数。

L8–L9：L8 导入 MovieLens 加载器；L9 导入 binarize，它实际使用严格大于阈值的判断。

L10–L11：L10 导入按用户分组的随机切分器；L11 导入官方 SAR 类，不能与项目自写的 SAR-style 混为一谈。

L12–L22：L12 打开多行导入括号，L22 关闭。L13–16 分别是 MAP、NDCG、Precision、Recall 排序指标；L17–18 是 RMSE、MAE 评分误差；L19 是二元 logloss；L20–21 是 R² 与解释方差。具体分母见后面的指标单元。

L23：store_metadata 把指标写入 Notebook 的结构化输出，供程序对照原值，不是另存数据库。

L25–L26：L25 加载 IPython 的 autoreload 扩展，L26 设为自动重载已导入模块。百分号命令只能在 IPython/Notebook 内核中使用，直接复制到普通 .py 会报语法错误。

L28–L30：三条 f-string 分别打印 Python、NumPy、pandas 版本。实跑环境为 Python 3.12.4、NumPy 1.26.4、pandas 2.2.3；主项目的另一套环境不能替代这里的内核。

空行 L6/L24/L27 仅分隔逻辑，不执行操作。

### SAR 原单元 6：固定推荐长度与数据规模

原单元 6 → 执行单元 7；L1–L5；单元源码 SHA-256 前 12 位 76fa279d4fb8。

这两个常量影响数据加载和后续评估；为了复现，先保留原值。

```python
# top k items to recommend
TOP_K = 10

# Select MovieLens data size: 100k, 1m, 10m, or 20m
MOVIELENS_DATA_SIZE = "100k"
```

L1–L2：L1 的注释说明推荐长度；L2 令每位用户最多得到 10 个推荐位置，指标也在 K=10 截断。

L4–L5：L4 列出加载器可选规模，L5 选 100k。这里不是独立扩展实验的 1M。

空行 L3 仅分隔逻辑，不执行操作。

### SAR 原单元 8：加载评分并减少内存

原单元 8 → 执行单元 9；L1–L8；单元源码 SHA-256 前 12 位 c495f5f4fa8e。

加载器返回含 userID、itemID、rating、timestamp 的表；本次共 100,000 行。执行副本在 L1 后增加一行 local_cache_path，见后面的映射说明。

```python
data = movielens.load_pandas_df(
    size=MOVIELENS_DATA_SIZE
)

# Convert the float precision to 32-bit in order to reduce memory consumption 
data["rating"] = data["rating"].astype(np.float32)

data.head()
```

L1–L3：L1 调用加载器，L2 把上一单元的 100k 传给 size，L3 结束调用。默认 header 保留四列；timestamp 是后续时间衰减需要的输入。

L5–L6：L5 解释类型转换目的；L6 只把 rating 列转成 32 位浮点数，不删评分、不改变 1–5 的数值。

L8：head() 在 Notebook 显示前 5 行，用来检查列名和类型。完整执行本保留了原始示例行，只在本地查看，本伴读不再刊载。

空行 L4/L7 仅分隔逻辑，不执行操作。

执行副本新增的 L2 是：

```python
    local_cache_path='H:\\Career_AI_Portfolio\\data\\movielens',
```

该行固定 H 盘缓存位置；原 L2 及之后的内容保持原样，映射到执行本时行号加 1。

### SAR 原单元 10：按用户随机切分

原单元 10 → 执行单元 11；L1–L1；单元源码 SHA-256 前 12 位 36d6ef620c18。

返回 train 与 test 两个 DataFrame。这里的 stratified 指按用户分组后随机分配，并不是按时间预测未来。

```python
train, test = python_stratified_split(data, ratio=0.75, col_user="userID", col_item="itemID", seed=42)
```

L1：data 是全部评分；ratio=0.75 是每位用户约 75% 进入训练；col_user/col_item 指明键列；seed=42 固定随机排序。每组有取整，汇总实际为 74,992/25,008，而不是恰好 75,000/25,000。

### SAR 原单元 11：打印切分规模

原单元 11 → 执行单元 12；L1–L18；单元源码 SHA-256 前 12 位 677baca84d10。

这一单元把真实数量代入字符串，帮助检查切分是否意外丢行或漏用户。它不参与训练。

代码 L1–L15（同一单元的连续片段）：

```python
print("""
Train:
Total Ratings: {train_total}
Unique Users: {train_users}
Unique Items: {train_items}

Test:
Total Ratings: {test_total}
Unique Users: {test_users}
Unique Items: {test_items}
""".format(
    train_total=len(train),
    train_users=len(train['userID'].unique()),
    train_items=len(train['itemID'].unique()),
    test_total=len(test),
```

代码 L16–L18（同一单元的连续片段）：

```python
    test_users=len(test['userID'].unique()),
    test_items=len(test['itemID'].unique()),
))
```

L1–L11：L1 开始三引号模板，L11 结束模板并调用 format。L2/7 是 Train/Test 标题；L3–5、L8–10 分别放行数、用户数、物品数；L6 是字符串内部的空白行，不是 Python 语句。

L12–L14：L12 取训练行数；L13 对 userID 去重计数；L14 对 itemID 去重计数。实测分别为 74,992、943、1,653。

L15–L18：L15–17 同样统计测试集，得到 25,008、943、1,444；L18 关闭 format 和 print。用户都出现过训练不代表所有测试物品都能推荐：有 35 条测试评分的物品不在训练目录。

### SAR 原单元 14：构造带时间衰减的 SAR

原单元 14 → 执行单元 15；L1–L13；单元源码 SHA-256 前 12 位 f048af4e7c45。

SAR（Simple Algorithm for Recommendation）通过用户历史亲和度和物品共同出现关系打分。实例化只保存配置；fit 才计算矩阵。

```python
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)-8s %(message)s')

model = SAR(
    col_user="userID",
    col_item="itemID",
    col_rating="rating",
    col_timestamp="timestamp",
    similarity_type="jaccard", 
    time_decay_coefficient=30, 
    timedecay_formula=True,
    normalize=True
)
```

L1–L2：L1 把日志设成 DEBUG；L2 在日志中显示时间、级别与消息，-8s 让级别字段左对齐。它只影响观察信息。

L4–L8：L4 开始构造模型；L5–8 分别把用户、物品、评分和时间列名告诉 SAR。列名拼错会在拟合时失败。

L9：jaccard 用共同用户数除以用户集合并集大小衡量两个物品的相似度，不是余弦相似度。

L10–L11：L10 的 30 是半衰期天数；L11 打开时间衰减。默认参考时间取训练表最大 timestamp，每隔 30 天权重约减半；不会使用现在的电脑日期。

L12–L13：L12 启用预测值的评分范围归一化；L13 结束构造。此设置不让分数成为经过校准的点击概率。

空行 L3 仅分隔逻辑，不执行操作。

### SAR 原单元 16：拟合模型并计时

原单元 16 → 执行单元 17；L1–L4；单元源码 SHA-256 前 12 位 eb4c94f3f8ae。

输入是 train。fit 在模型内建立索引、亲和度与物品相似度；不会把测试评分拟合进去。

```python
with Timer() as train_time:
    model.fit(train)

print("Took {} seconds for training.".format(train_time.interval))
```

L1–L2：L1 进入计时上下文并命名 train_time；L2 调用 model.fit(train)，缩进表示只计量这一块。

L4：读取 train_time.interval 并打印秒数。本次为约 0.310 秒；硬件、库版本和调度会影响时间，复现验收比较的是排序指标。

空行 L3 仅分隔逻辑，不执行操作。

### SAR 原单元 17：给测试用户生成推荐

原单元 17 → 执行单元 18；L1–L4；单元源码 SHA-256 前 12 位 d4964e0b0e73。

传 test 是为了取得用户 ID；该方法用已经训练好的矩阵给这些用户打分，不把 test.rating 当特征。

```python
with Timer() as test_time:
    top_k = model.recommend_k_items(test, top_k=TOP_K, remove_seen=True)

print("Took {} seconds for prediction.".format(test_time.interval))
```

L1–L2：L1 开始预测计时；L2 为测试表中各用户取 top10，remove_seen=True 过滤训练中已出现的用户–物品对。返回表含 userID、itemID、prediction。

L4：打印 test_time.interval，实测约 0.292 秒；top_k 实际有 9,430 行，即 943×10。

空行 L3 仅分隔逻辑，不执行操作。

### SAR 原单元 18：检查推荐表结构

原单元 18 → 执行单元 19；L1–L1；单元源码 SHA-256 前 12 位 a0a1d5cf6d9e。

显示的是预测表样例，不是指标，也不是完整推荐目录。

```python
top_k.head()
```

L1：head() 只展示前 5 行，便于确认 prediction 列存在。不要把这几行当总体效果的证据。

### SAR 原单元 20：计算四项排序指标

原单元 20 → 执行单元 21；L1–L5；单元源码 SHA-256 前 12 位 ac294a93fa7a。

test 是真值，top_k 是推荐。此原版 SAR 没有先删掉低评分：默认 binary 相关性把测试表中出现的物品视为相关。传 col_rating 不会自动执行 rating≥4。

```python
# Ranking metrics
eval_map = map_at_k(test, top_k, col_user="userID", col_item="itemID", col_rating="rating", k=TOP_K)
eval_ndcg = ndcg_at_k(test, top_k, col_user="userID", col_item="itemID", col_rating="rating", k=TOP_K)
eval_precision = precision_at_k(test, top_k, col_user="userID", col_item="itemID", col_rating="rating", k=TOP_K)
eval_recall = recall_at_k(test, top_k, col_user="userID", col_item="itemID", col_rating="rating", k=TOP_K)
```

L1：注释划分排序指标区块，与下一单元的评分误差区分。

L2：map_at_k 先计算每个命中位置的 Precision@r，再按 min(K, 真值物品数) 归一化并对用户取平均。此固定版本的 map_at_k 与分母用全部真值数量的 map 函数不同。

L3：ndcg_at_k 对前面位置的命中给更大权重，再除以该用户理想排序的 DCG。默认 score_type=binary、discfun_type=loge；DCG 与 IDCG 同时换为 log2 不改变比例。

L4：precision_at_k 计算命中数/K，再对可共同评估用户平均；不是“预测评分准确的百分比”。

L5：recall_at_k 计算命中数/该用户全部测试真值数量，再平均。本协议没有提前删除训练目录外的测试物品，所以不能套用独立 1M 实验的可达目标分母。


这里用 h_r 表示第 r 个推荐是否命中（0 或 1），R_u 是用户 u 在原测试表中的物品集合。Precision@r 是截至 r 的命中比例。下式是本固定版本 map_at_k 的分母：

$$AP@K=\frac{\sum_{r=1}^{K}h_r\,Precision@r}{\min(K,|R_u|)}$$

再对评估用户取平均得到 MAP。Precision@K 的分母是 K；Recall@K 的分母是该用户全部真值物品数量。NDCG 把命中折扣之和除以同一用户的理想折扣之和：

$$NDCG@K=\frac{\sum_{r=1}^{K}h_r/\log(1+r)}{\sum_{r=1}^{\min(K,|R_u|)}1/\log(1+r)}$$

教学手算：K=3，真值有 2 个物品，推荐命中序列为 [1,0,1]。Precision=2/3，Recall=1，AP=(1+2/3)/2=5/6；NDCG=(1+1/2)/(1+1/log2(3))≈0.9197。这里是自造小例子，不是用户 54 的真实结果。


### SAR 原单元 21：评分误差到底测了哪些行

原单元 21 → 执行单元 22；L1–L5；单元源码 SHA-256 前 12 位 3df70c59890f。

这些函数先按 userID、itemID 对 test 与 top_k 做内连接（inner join）。因此只评价两表交集中的评分预测，不是在全部 25,008 条测试评分上预测 RMSE。

```python
# Rating metrics
eval_rmse = rmse(test, top_k, col_user="userID", col_item="itemID", col_rating="rating")
eval_mae = mae(test, top_k, col_user="userID", col_item="itemID", col_rating="rating")
eval_rsquared = rsquared(test, top_k, col_user="userID", col_item="itemID", col_rating="rating")
eval_exp_var = exp_var(test, top_k, col_user="userID", col_item="itemID", col_rating="rating")
```

L1：注释表明下面测评分数值误差，而不是推荐顺序。

L2：RMSE 是误差平方均值再开根号，大误差受罚更重；本次为 1.229246。

L3：MAE 是绝对误差均值，单位仍是评分分数；本次为 1.033912。

L4：R²=1−残差平方和/真值离均差平方和；本次 −0.511334，表示在该交集上按平方误差衡量，还不如用交集真值均值预测。负值不是程序自动报错。

L5：解释方差为 1−Var(y−ŷ)/Var(y)；本次 0.098494。它用残差方差，R²用残差平方和；存在系统性偏移时两者可以明显不同。

### SAR 原单元 22：二值化与 logloss 的边界

原单元 22 → 执行单元 23；L1–L10；单元源码 SHA-256 前 12 位 1fc51e02ee33。

此单元是原版额外演示，不参与我们用来声明复现的 8 项排序指标，也不参与选择扩展模型。

```python
positivity_threshold = 2
test_bin = test.copy()
test_bin["rating"] = binarize(test_bin["rating"], positivity_threshold)

top_k_prob = top_k.copy()
top_k_prob["prediction"] = minmax_scale(top_k_prob["prediction"].astype(float))

eval_logloss = logloss(
    test_bin, top_k_prob, col_user="userID", col_item="itemID", col_rating="rating"
)
```

L1–L3：L1 设阈值 2；L2 复制 test 避免改掉后续原评分；L3 使用严格 rating>2 得到 0/1，所以评分 2 仍是 0。这不是 BPR 的阈值 3.5。

L5–L6：L5 复制预测表；L6 先转浮点，再对所有用户的 prediction 整列做 min–max 缩放。缩到 [0,1] 只是数值变换，不能据此断言预测已校准为概率。

L8–L10：L8 调用 logloss，L9 传入二值真值与缩放预测并声明键列，L10 结束。底层仍先按键内连接，再计算二元交叉熵；本次 0.569153。不要把它解释成全面评价未曝光项目的概率模型。

空行 L4/L7 仅分隔逻辑，不执行操作。


用 y 表示交集中的真实评分，ŷ 表示对应 prediction，n 为交集行数，则 RMSE 是平方误差平均后开根号，MAE 是绝对误差的平均。不要因 normalize=True 就把 SAR 视为专业评分回归器：原项目也说明它主要面向排序。

$$RMSE=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat y_i)^2},\qquad MAE=\frac{1}{n}\sum_{i=1}^{n}|y_i-\hat y_i|$$

logloss 的 y 改成 0/1、p 改成缩放值后，单行损失为 −y log(p)−(1−y)log(1−p)。库对数值端点有处理，不能手工把 log(0) 当成项目真实输出。本例只示范调用；未经校准、且只在推荐与真值交集上评价，不能据此得出整体点击概率质量。


### SAR 原单元 23：格式化打印结果

原单元 23 → 执行单元 24；L1–L12；单元源码 SHA-256 前 12 位 a00078d3fea7。

这里读取已有变量，未再训练或重新计算。屏幕六位小数是展示精度；JSON 保留更多位数。

```python
print("Model:\t",
      "Top K:\t%d" % TOP_K,
      "MAP@K:\t%f" % eval_map,
      "NDCG@K:\t%f" % eval_ndcg,
      "Precision@K:\t%f" % eval_precision,
      "Recall@K:\t%f" % eval_recall,
      "RMSE:\t%f" % eval_rmse,
      "MAE:\t%f" % eval_mae,
      "R2:\t%f" % eval_rsquared,
      "Exp var:\t%f" % eval_exp_var,
      "Logloss:\t%f" % eval_logloss,
      sep='\n')
```

L1–L2：L1 打印 Model 标签；L2 用 %d 输出整数 K。此单元没有给 Model 标签填模型名称，是上游原写法。

L3–L6：L3–6 依次显示 MAP、NDCG、Precision、Recall；%f 默认保留小数点后 6 位，打印变短不代表底层指标被截断。

L7–L11：L7–11 依次显示 RMSE、MAE、R²、解释方差、logloss，变量来自前两个单元。

L12：sep='\n' 指定各个 print 参数换行输出，并关闭调用。

### SAR 原单元 24：用户 54 的局部诊断

原单元 24 → 执行单元 25；L1–L11；单元源码 SHA-256 前 12 位 dd603e1a9f01。

这个例子教你追踪某一个用户，不能代替整体评价，也不能在简历上把一次手选案例写成总体提升。

```python
# Now let's look at the results for a specific user
user_id = 54

ground_truth = test[test["userID"] == user_id].sort_values(
    by="rating", ascending=False
)[:TOP_K]
prediction = model.recommend_k_items(
    pd.DataFrame(dict(userID=[user_id])), remove_seen=True
)
df = pd.merge(ground_truth, prediction, on=["userID", "itemID"], how="left")
df.head(10)
```

L1–L2：L1 是原作者的示例注释；L2 固定数据集里的 user_id=54，不代表当前使用者。

L4–L6：L4 只取用户 54 的测试行并开始排序；L5 按真实 rating 降序；L6 取前 TOP_K 行。ground_truth 是该用户评分最高的一组测试行，不等于模型的推荐顺序。

L7–L9：L7 调推荐方法；L8 构造只有 userID 一列的一行 DataFrame，并过滤训练已看物品；L9 结束。这里没显式传 top_k，官方默认也是 10。

L10：以 ground_truth 为左表，按用户与物品键 left join。每条真值保留；某条 prediction 为 NaN，表示它没进入该次推荐表，不表示模型分数等于 0。

L11：显示合并表前 10 行，便于肉眼看哪些高评分测试电影被推荐到了。原始逐用户内容仅在本地执行本查看。

空行 L3 仅分隔逻辑，不执行操作。

### SAR 原单元 26：把排序指标存入 Notebook 输出

原单元 26 → 执行单元 27；L1–L7；单元源码 SHA-256 前 12 位 45baa5dbfe89。

结构化 metadata 使复现脚本可以按指标名称读数字，避免从打印文字中猜测。

```python
# Record results for tests - ignore this cell
store_metadata("map", eval_map)
store_metadata("ndcg", eval_ndcg)
store_metadata("precision", eval_precision)
store_metadata("recall", eval_recall)
store_metadata("train_time", train_time.interval)
store_metadata("test_time", test_time.interval)
```

L1：原注释让一般读者忽略此单元；复现与审计时它很重要，不能跳过。

L2–L5：L2–5 分别存 map、ndcg、precision、recall。键名是比较脚本的契约；改变键名会找不到原指标。

L6–L7：L6/7 保存训练/预测秒数。时间也被记录，但不要求与上游保存时间完全相同。

### BPR 原单元 4：导入 Cornac 与上游包装类

原单元 4 → 执行单元 5；L1–L14；单元源码 SHA-256 前 12 位 981dd5fc9529。

模型实现来自 Cornac；Recommenders 的 BPR 子类增加 recommend_k_items 便利方法。两者名称相似，作用不同。

```python
import sys
import cornac

from recommenders.datasets import movielens
from recommenders.datasets.python_splitters import python_random_split
from recommenders.evaluation.python_evaluation import map_at_k, ndcg_at_k, precision_at_k, recall_at_k
from recommenders.models.cornac.bpr import BPR
from recommenders.utils.timer import Timer
from recommenders.utils.constants import SEED
from recommenders.utils.python_utils import binarize
from recommenders.utils.notebook_utils import store_metadata

print(f"System version: {sys.version}")
print(f"Cornac version: {cornac.__version__}")
```

L1–L2：L1 读取 Python 版本；L2 导入 cornac 包，提供数据结构与底层模型，并读取版本。

L4–L5：L4 导入数据加载器；L5 导入全表随机切分器。它与 SAR 的按用户随机切分不同。

L6：导入四个排序指标，后面使用它们的默认 userID、itemID、rating 列名。

L7：BPR 是 Recommenders 包装的 Cornac BPR 子类；它保留底层训练，并补充批量推荐接口。

L8–L9：L8 导入上下文计时器；L9 导入常量 SEED，固定源码里数值为 42。

L10–L11：L10 导入严格大于阈值的 binarize；L11 导入结构化指标输出工具。

L13–L14：L13/14 打印解释器和 Cornac 版本。本次 baseline 使用 Cornac 2.3.0，不能换成根环境的 3.0.1 后仍宣称相同环境。

空行 L3/L12 仅分隔逻辑，不执行操作。

### BPR 原单元 5：固定正反馈标准与模型大小

原单元 5 → 执行单元 6；L1–L12；单元源码 SHA-256 前 12 位 8fa8e396a7b9。

这里把显式评分转成隐式正反馈，目标是把正样本排在抽到的比较物品前面，而非预测评分为几星。

```python
# Select MovieLens data size: 100k, 1m, 10m, or 20m
MOVIELENS_DATA_SIZE = "100k"

# top k items to recommend
TOP_K = 10

# Minimum rating to consider as positive implicit feedback
RATING_THRESHOLD = 3.5

# Model parameters
NUM_FACTORS = 200
NUM_EPOCHS = 200
```

L1–L2：注释列出可选规模；MOVIELENS_DATA_SIZE 固定为 100k。

L4–L5：TOP_K=10 只规定推荐评估截断；并不等于后面的批量预测只返回 10 个物品。

L7–L8：RATING_THRESHOLD=3.5 配合严格大于判断；评分是整数，因此保留 4、5 分，丢弃 1、2、3 分。

L10–L12：L10 注释开始模型参数区；L11 设每个用户/物品的隐因子维度为 200；L12 最多训练 200 轮。不要误记成扩展模型的 64 维、100 轮。

空行 L3/L6/L9 仅分隔逻辑，不执行操作。

### BPR 原单元 9：加载后只保留正反馈

原单元 9 → 执行单元 10；L1–L9；单元源码 SHA-256 前 12 位 4c9db38e303c。

加载器只返回三列，后面才能直接把每行交给 from_uir。原始 100,000 行经过筛选剩 55,375 行。

```python
data = movielens.load_pandas_df(
    size=MOVIELENS_DATA_SIZE,
    header=["userID", "itemID", "rating"]
)


data['rating'] = binarize(data['rating'].values, RATING_THRESHOLD)
data = data[data['rating'] > 0].reset_index(drop=True)
data.head()
```

L1–L4：L1 调用加载器；L2 传 100k；L3 指定 userID、itemID、rating 三列，省去 timestamp；L4 结束调用。执行本同样在 L1 后加本地缓存参数。

L7：把评分数组按 >3.5 转成 1.0/0.0，覆盖 rating 列。原 4 分和 5 分都变成 1，强度差异不再进入这个 BPR 实验。

L8：只留下 rating>0 的行，reset_index(drop=True) 重新编号而不把旧索引加入新列。

L9：显示前 5 行检查三列结构与二元标签；不在伴读重印数据样本。

空行 L5/L6 仅分隔逻辑，不执行操作。

执行副本新增的 L2 是：

```python
    local_cache_path='H:\\Career_AI_Portfolio\\data\\movielens',
```

该行固定 H 盘缓存位置；原 L2 及之后的内容保持原样，映射到执行本时行号加 1。

### BPR 原单元 10：全表随机切分

原单元 10 → 执行单元 11；L1–L1；单元源码 SHA-256 前 12 位 b4baa27b804b。

这个协议从筛选后的正反馈表随机取 75% 训练，并没有保证每位用户的比例恰好一致。

```python
train, test = python_random_split(data, 0.75)
```

L1：python_random_split(data,0.75) 返回 41,531 行 train 与 13,844 行 test。seed 没写在调用里，但固定函数的默认值为 42；真实时间戳已不在三列表中。

### BPR 原单元 12：把 DataFrame 变成 Cornac 数据集

原单元 12 → 执行单元 13；L1–L4；单元源码 SHA-256 前 12 位 9fdc90df8589。

UIR 指 User–Item–Rating。Cornac 会把原始 ID 映射为紧凑的内部行列编号，这些内部编号不是 MovieLens 的 ID。

```python
train_set = cornac.data.Dataset.from_uir(train.itertuples(index=False), seed=SEED)

print('Number of users: {}'.format(train_set.num_users))
print('Number of items: {}'.format(train_set.num_items))
```

L1：itertuples(index=False) 逐行产生 userID、itemID、rating 三元组，不附带 pandas 索引；from_uir 建立稀疏交互矩阵及 ID 字典，seed=SEED 固定数据集随机状态。

L3–L4：L3/4 打印训练中的用户/物品数量，实测 942 和 1,395。测试有 930 名用户，均在训练出现；另有 63 条测试行的物品不在训练目录。

空行 L2 仅分隔逻辑，不执行操作。

### BPR 原单元 14：构造 BPR 模型

原单元 14 → 执行单元 15；L1–L8；单元源码 SHA-256 前 12 位 6a4e2d15d391。

BPR（Bayesian Personalized Ranking）以用户对正样本和比较物品的分差优化成对排序；训练细节与梯度勘误见主手册。

```python
bpr = BPR(
    k=NUM_FACTORS,
    max_iter=NUM_EPOCHS,
    learning_rate=0.01,
    lambda_reg=0.001,
    verbose=True,
    seed=SEED
)
```

L1–L3：L1 构造对象；L2 传 200 维；L3 传 200 轮。只构造对象不会完成学习。

L4–L5：L4 的 learning_rate=0.01 控制每次更新步长；L5 的 lambda_reg=0.001 控制正则强度。保持上游参数才能比较其保存值。

L6–L8：L6 打开训练进度输出；L7 传随机种子 42；L8 结束调用。未显式给出的 use_bias 等参数使用此固定 Cornac 版本默认值，不能随手用新版接口推断。

### BPR 原单元 15：拟合稀疏交互并计时

原单元 15 → 执行单元 16；L1–L3；单元源码 SHA-256 前 12 位 f2667de4ac8e。

fit 会实际执行 BPR 更新；比较物品从未被当作该用户正反馈的物品中抽取。未知反馈不等于已经证实不喜欢。

```python
with Timer() as t:
    bpr.fit(train_set)
print(f"Took {t} seconds for training.")
```

L1–L2：L1 把计时器命名为 t；L2 在上下文中拟合 train_set。用户因子、物品因子与 item bias 保存在 bpr 对象里。

L3：f-string 调用 Timer 的字符串表示，打印训练用时。下一计时单元会覆盖变量 t，所以它不长期同时保存训练与预测两个用时。

### BPR 原单元 17：为训练用户计算未见物品分数

原单元 17 → 执行单元 18；L1–L3；单元源码 SHA-256 前 12 位 387bbe5b3571。

本单元返回的是全部未见候选分数，评估函数稍后才截前 10。这样的大表在更大目录上会成为内存和计算开销。

```python
with Timer() as t:
    all_predictions = bpr.recommend_k_items(train, col_user='userID', col_item='itemID', remove_seen=True)
print(f"Took {t} seconds for prediction.")
```

L1–L2：L1 开始计时；L2 将 train 传给包装方法，声明键列并过滤训练正反馈已见对。没有传 top_k，而方法默认 top_k=None，所以保留每位训练用户的全部有限候选，实测 1,272,559 行。

L3：打印预测秒数。底层使用用户因子×物品因子转置并加 item bias；传入 train 的用户–物品键用于 seen 过滤。

### BPR 原单元 18：查看批量预测的列

原单元 18 → 执行单元 19；L1–L1；单元源码 SHA-256 前 12 位 d264045df8f2。

这一步只观察已经算好的结果，不改变排序。

```python
all_predictions.head()
```

L1：head() 显示预测表前 5 行，确认 prediction 为数值且 ID 列可与 test 对齐；不得把样例表上传成公开原始数据。

### BPR 原单元 19：截前 10 并计算排序指标

原单元 19 → 执行单元 20；L1–L12；单元源码 SHA-256 前 12 位 1792705069e6。

输入 all_predictions 虽然很长，四个指标都明确使用 k=TOP_K。标签已在此前筛选为正反馈，因此与 SAR 的“全部测试评分为相关”不同。

```python
eval_map = map_at_k(test, all_predictions, col_prediction='prediction', k=TOP_K)
eval_ndcg = ndcg_at_k(test, all_predictions, col_prediction='prediction', k=TOP_K)
eval_precision = precision_at_k(test, all_predictions, col_prediction='prediction', k=TOP_K)
eval_recall = recall_at_k(test, all_predictions, col_prediction='prediction', k=TOP_K)


print(f"Model:",
      f"Top K:\t\t {TOP_K}",
      f"MAP@K:\t\t {eval_map:f}",
      f"NDCG@K:\t\t {eval_ndcg:f}",
      f"Precision@K:\t {eval_precision:f}",
      f"Recall@K:\t {eval_recall:f}", sep="\n")
```

L1–L4：L1–4 分别计算 MAP、NDCG、Precision、Recall。col_prediction 指定分数列；用户/物品列用默认名称；k=10 使评估器先按每位用户分数截前 10。公式同 SAR 指标说明，但目标集合与切分不同，不能据此排列两模型优劣。

L7–L8：L7 打印 Model 标签；L8 打印整数 K，\t 是制表字符，只影响文本对齐。

L9–L12：L9–12 用 :f 显示四项浮点指标，最后 sep='\n' 令输出逐项换行。完整值保存在结构化 metadata 中。

空行 L5/L6 仅分隔逻辑，不执行操作。

### BPR 原单元 20：保存四项排序指标

原单元 20 → 执行单元 21；L1–L5；单元源码 SHA-256 前 12 位 9f4b770cf9bd。

这四个键与 SAR 相同，复现脚本因此能用统一读取逻辑比较两份原 Notebook 各自的结果。

```python
# Record results for tests - ignore this cell
store_metadata("map", eval_map)
store_metadata("ndcg", eval_ndcg)
store_metadata("precision", eval_precision)
store_metadata("recall", eval_recall)
```

L1：保留原注释；审计时需要执行本单元，不能因注释写了 ignore 就省略。

L2–L5：L2–5 依次记录 map、ndcg、precision、recall 到 Notebook 的富输出中，不写入评分文件，也不改变模型。


### 两个缓存参数与四个辅助单元

执行副本对 SAR 原单元 8 与 BPR 原单元 9 做同一种插入：在调用 load_pandas_df 的第一行之后增加 local_cache_path。这把下载与缓存定位到 H 盘，不改变 zip 字节、标签、切分参数或算法。原 L1 仍是执行 L1，新增缓存行为执行 L2，原 L2 及以后对应执行 L3 及以后；两个单元的每行映射都写入 manifest。

其余新增代码是各执行本首尾的两个辅助单元。下面完整解释这四个单元；它们的代码来自本项目，不属于上游原单元。先看导入路径，再看证据导出，便能分清“模型本身”和“怎样证明模型跑过”。


### SAR 本地辅助单元：固定源码导入路径

本地辅助单元 → 执行单元 1；L1–L3；单元源码 SHA-256 前 12 位 1ff5b1b7a58a。

此单元来自本项目的 run_upstream.py，不是上游算法改写。

```python
import sys
sys.path.insert(0, 'H:\\Career_AI_Portfolio\\external\\recommenders')
print('Pinned source commit: aa8332189cd495be6ffaa7e1c8054f1c180b5ef3')
```

L1：导入 sys，准备调整此内核进程的模块搜索顺序。

L2：把固定源码 checkout 插到 sys.path 第 0 位，保证 import recommenders 读取本次核验过的目录，不是机器上的另一个安装版本。Windows 路径中的双反斜杠是字符串转义。

L3：打印预期固定提交，帮助阅读输出。打印本身不能证明磁盘确实在该提交；runner 在执行前另用 git rev-parse 与 git diff 进行真实检查。

### SAR 本地辅助单元：导出本次执行证据

本地辅助单元 → 执行单元 28；L1–L22；单元源码 SHA-256 前 12 位 83b4986a792a。

此单元来自本项目的 run_upstream.py，不是上游算法改写。

代码 L1–L15（同一单元的连续片段）：

```python
import json, hashlib
from pathlib import Path
def frame_hash(frame):
    return hashlib.sha256(frame.to_csv(index=False, lineterminator='\n').encode()).hexdigest()
details = {
 'train_rows': len(train), 'test_rows': len(test),
 'train_users': int(train.userID.nunique()), 'test_users': int(test.userID.nunique()),
 'train_items': int(train.itemID.nunique()), 'test_items': int(test.itemID.nunique()),
 'common_train_test_users': len(set(train.userID) & set(test.userID)),
 'test_only_users': len(set(test.userID) - set(train.userID)),
 'test_rows_item_absent_from_train': int((~test.itemID.isin(train.itemID)).sum()),
 'train_sha256': frame_hash(train), 'test_sha256': frame_hash(test),
 'data_rows': len(data), 'seed': 42,
 'metrics': {'map': float(eval_map), 'ndcg': float(eval_ndcg),
             'precision': float(eval_precision), 'recall': float(eval_recall)}
```

代码 L16–L22（同一单元的连续片段）：

```python
}
details['rating_metrics'] = {key: float(value) for key,value in {'rmse':eval_rmse,'mae':eval_mae,'r2':eval_rsquared,'explained_variance':eval_exp_var,'logloss':eval_logloss}.items()}
details['train_seconds'] = train_time.interval
details['prediction_seconds'] = test_time.interval
details['prediction_rows'] = len(top_k)
Path('H:\\Career_AI_Portfolio\\projects\\01_recommendation_service\\reports\\baseline\\sar_run_details.json').write_text(json.dumps(details, indent=2), encoding='utf-8')
print(details)
```

L1–L2：L1 导入 JSON 与 SHA-256 工具；L2 导入 Path 用于文件写入。它们不参与模型打分。

L3–L4：L3 定义 frame_hash；L4 把表按当前行序导出为不含索引、换行固定为 \n 的 CSV 字节，再计算 SHA-256。这里保存的是摘要，不把评分表写成公共文件。

L5–L6：L5 开始 evidence 字典；L6 保存训练与测试的行数。变量 train/test 已由原单元创建。

L7–L8：L7 保存去重用户数，L8 保存去重物品数；int 将 NumPy 计数转成可直接 JSON 序列化的 Python 整数。

L9–L10：L9 对训练/测试用户集合取交集，L10 取测试减训练的差集，分别记录共同用户与只在测试出现的用户数量。

L11：isin 判断测试物品是否存在于训练物品中，~ 取反，sum 计数；这是训练目录外测试行数量，不是测试冷用户数。

L12–L13：L12 记录训练/测试表哈希；L13 保存当前 data 行数和 seed=42。SAR 的 data 仍为原始 100,000 行，没有先按评分阈值过滤。seed 字段是已核实的参数记录，不在此重设随机数。

L14–L16：L14/15 保存四项已算出的排序指标，float 兼容 JSON 数值；L16 关闭字典。不会把指标重新算一次。

L17：用字典推导式逐项保存 RMSE、MAE、R²、解释方差和 logloss，所有值转成 float；这些是原单元实际运行结果。

L18–L19：L18/19 分别保存训练和预测计时器的 interval。计时不同不等于排序复现失败。

L20：记录 top_k 表行数，用于核对用户数乘推荐长度。

L21–L22：L21 以 UTF-8 将 details 格式化写入 sar_run_details.json；L22 在 Notebook 再显示字典。只有汇总数量、指标与哈希，不包含逐用户评分。

### BPR 本地辅助单元：固定源码导入路径

本地辅助单元 → 执行单元 1；L1–L3；单元源码 SHA-256 前 12 位 1ff5b1b7a58a。

此单元来自本项目的 run_upstream.py，不是上游算法改写。

```python
import sys
sys.path.insert(0, 'H:\\Career_AI_Portfolio\\external\\recommenders')
print('Pinned source commit: aa8332189cd495be6ffaa7e1c8054f1c180b5ef3')
```

L1：导入 sys，准备调整此内核进程的模块搜索顺序。

L2：把固定源码 checkout 插到 sys.path 第 0 位，保证 import recommenders 读取本次核验过的目录，不是机器上的另一个安装版本。Windows 路径中的双反斜杠是字符串转义。

L3：打印预期固定提交，帮助阅读输出。打印本身不能证明磁盘确实在该提交；runner 在执行前另用 git rev-parse 与 git diff 进行真实检查。

### BPR 本地辅助单元：导出本次执行证据

本地辅助单元 → 执行单元 23；L1–L19；单元源码 SHA-256 前 12 位 c833d50d9ca0。

此单元来自本项目的 run_upstream.py，不是上游算法改写。

代码 L1–L15（同一单元的连续片段）：

```python
import json, hashlib
from pathlib import Path
def frame_hash(frame):
    return hashlib.sha256(frame.to_csv(index=False, lineterminator='\n').encode()).hexdigest()
details = {
 'train_rows': len(train), 'test_rows': len(test),
 'train_users': int(train.userID.nunique()), 'test_users': int(test.userID.nunique()),
 'train_items': int(train.itemID.nunique()), 'test_items': int(test.itemID.nunique()),
 'common_train_test_users': len(set(train.userID) & set(test.userID)),
 'test_only_users': len(set(test.userID) - set(train.userID)),
 'test_rows_item_absent_from_train': int((~test.itemID.isin(train.itemID)).sum()),
 'train_sha256': frame_hash(train), 'test_sha256': frame_hash(test),
 'data_rows': len(data), 'seed': 42,
 'metrics': {'map': float(eval_map), 'ndcg': float(eval_ndcg),
             'precision': float(eval_precision), 'recall': float(eval_recall)}
```

代码 L16–L19（同一单元的连续片段）：

```python
}
details['prediction_rows'] = len(all_predictions)
Path('H:\\Career_AI_Portfolio\\projects\\01_recommendation_service\\reports\\baseline\\bpr_run_details.json').write_text(json.dumps(details, indent=2), encoding='utf-8')
print(details)
```

L1–L2：L1 导入 JSON 与 SHA-256 工具；L2 导入 Path 用于文件写入。它们不参与模型打分。

L3–L4：L3 定义 frame_hash；L4 把表按当前行序导出为不含索引、换行固定为 \n 的 CSV 字节，再计算 SHA-256。这里保存的是摘要，不把评分表写成公共文件。

L5–L6：L5 开始 evidence 字典；L6 保存训练与测试的行数。变量 train/test 已由原单元创建。

L7–L8：L7 保存去重用户数，L8 保存去重物品数；int 将 NumPy 计数转成可直接 JSON 序列化的 Python 整数。

L9–L10：L9 对训练/测试用户集合取交集，L10 取测试减训练的差集，分别记录共同用户与只在测试出现的用户数量。

L11：isin 判断测试物品是否存在于训练物品中，~ 取反，sum 计数；这是训练目录外测试行数量，不是测试冷用户数。

L12–L13：L12 记录训练/测试表哈希；L13 保存当前 data 行数和 seed=42。BPR 的 data 已经过正反馈过滤，实际为 55,375 行。seed 字段是已核实的参数记录，不在此重设随机数。

L14–L16：L14/15 保存四项已算出的排序指标，float 兼容 JSON 数值；L16 关闭字典。不会把指标重新算一次。

L17：记录 all_predictions 的行数；没有把所有预测明细写入 JSON。

L18–L19：L18 写入 bpr_run_details.json，indent=2 方便阅读；L19 显示汇总字典。BPR 原计时变量 t 被复用，所以此单元没有仿造不存在的独立训练时间字段。


### 实测结果与练习核对

| 原版实验 | MAP@10 | NDCG@10 | Precision@10 | Recall@10 |
|---|---:|---:|---:|---:|
| SAR 100K | 0.2447220531 | 0.3795334515 | 0.3310710498 | 0.1768368472 |
| BPR 100K | 0.1803676443 | 0.3051899537 | 0.2390322581 | 0.2086604438 |

每个实测值与自己固定 Notebook 的保存值逐项相同。SAR 用全评分与每用户随机切分，BPR 用评分>3.5 的正反馈与全表随机切分，所以表格只核对复现，不给算法排优劣。README 总表曾列出另一组 SAR NDCG 0.3938；验收依据是本固定 Notebook 的 0.3795334515，不能把总表数字移过来冒充同协议结果。

独立 1M 时间实验另外定义训练目录、可达目标、冷用户与验证选参。不要把上游随机切分的分数与它的时间测试分数拼成“提升曲线”。原 BPR Markdown 展示的梯度符号存在问题，已经保留原文并在主手册解释：实际 Cornac 2.3.0 更新使用正确的似然与负正则项，有限差分核验另见 reports/baseline/bpr_gradient_check.json。忠实执行代码不等于认可原说明里的每个公式。

自检 1：SAR 中把 positivity_threshold 改成 3.5，会改变前面的四项排序结果吗？答案：在这份顺序里不会；它只改 logloss 演示副本，前面的排序使用原 test。自检 2：BPR 的 TOP_K=10 为什么还生成一百多万行预测？答案：模型调用省略 top_k，包装方法默认返回所有未见候选；评估器才截前 10。自检 3：用户 54 合并表里 NaN 是预测 0 分吗？答案：不是，它表示左表该真值键没有匹配到本次推荐表。

完成这些辨析后，再回到自己的 1M 代码伴读：检查候选与 seen 过滤、验证选参和服务快照的边界。你应能从一个结果追溯到数据、具体单元和实际行号；仅能复述最终指标还不足以说明你能独立维护项目。
