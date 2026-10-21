# 项目1：求职表达与证据边界

这个项目针对 Data Scientist、Machine Learning Engineer 和偏模型落地的 AI Engineer。它把数据处理、排序模型、实验设计、数学取舍、接口和容器部署连成一条可以当场演示的链。

## 输入、输出和痛点

输入是 MovieLens 1M 的匿名历史评分与电影类别；离线输出是可复跑的排序评测和不确定性区间；服务输出是给定用户、数量、类别约束后的推荐列表。问题是：热门推荐覆盖有限，个性化排序又可能继续偏向热门内容。我们在验证集设定精度损失约束，再检验长尾重排是否带来可接受的取舍。

这项扩展确实提高了测试集长尾曝光，但也降低了 NDCG。保留这个结果，能说明你知道优化目标会冲突，也知道不能用一张漂亮截图代替评测。

## 可改写进英文简历的版本

以下描述对应已运行的项目成果。面试前应完成教案练习并独立重跑，能解释每个数字的分母、比较对象和限制；AI 协助完成的代码不能自动证明个人已经掌握。

- Built and containerized a FastAPI recommendation service with cold-start fallback, typed API contracts, readiness checks and a browser demo; validated HTTP ranking parity against a locally trained BPR artifact.
- Evaluated popularity, SAR-style and BPR rankers on 1.0M MovieLens ratings using a chronological split and full-catalog ranking; BPR achieved NDCG@10 of 0.2441 versus 0.2078 for popularity across 922 eligible warm test users.
- Selected novelty reranking under a validation accuracy constraint; increased held-out long-tail exposure from 1.84% to 2.28% with a 1.31% relative NDCG loss, reporting paired bootstrap intervals and cold-user coverage separately.

不写“生产系统”“为大公司服务”“提升营收”“发明 BPR”或“完美复现所有原指标”。上游数字是否匹配，必须看独立基线报告；扩展使用另一套时间协议。

## 30秒中文介绍

“我做了一个可以实际调用的推荐服务。先复现开源的经典推荐模型，再用一百万条历史评分做时间顺序评测，避免把未来信息放进训练。BPR 的排序表现比热门推荐好。我又研究了一个业务取舍：怎样让不那么热门的内容获得更多曝光，同时控制精度损失。最后把模型做成了带冷启动、输入校验和监控指标的 Docker API，也保留了能复跑的实验和失败结果。”

## 招聘者能检查什么

HR 能快速看到项目对应的岗位、工具和可运行入口。技术面试官可以继续检查训练/测试边界、候选集、BPR目标、ID重排、重排约束、置信区间和服务失败行为。项目的价值来自这些可核验的证据；不能保证任何招聘者一定喜欢或据此录用。

## 面试前必须能独立回答

1. 为什么用户 1 是冷用户，1161 是暖用户？时间划分如何产生这一结果？
2. 为什么评分未出现不能直接当作“不喜欢”？BPR仍使用负采样意味着什么假设？
3. 用三个物品手算一次 DCG、IDCG 和 NDCG；为什么 Recall 的分母不同？
4. 推导一次 BPR 梯度，说明 L2 正则项的符号，解释有限差分检查。
5. 为什么重排权重只能用验证集选择？为什么需要同时汇报 NDCG 损失？
6. 解释 bootstrap 的抽样单位、配对原因、区间不能涵盖的变异。
7. 为什么 `/health` 可以200而`/ready`是503？如何定位缺失模型？
8. 能否只看32毫秒P95便说“生产级”？为什么不能？

## 接到项目2

项目1训练并部署一个确定的排序模型。项目2将增加一个可靠的业务分析 Agent：工具调用、SQL/指标验证、检索证据、执行状态与失败恢复。复用这里的输入输出契约、评测、版本和可观测性思路；不要把这个项目单独包装一个聊天壳就当成第二个项目。项目2须在本项交付后另行推进。
