# Project 1 教学材料：从这里开始

本地位置：`H:\Career_AI_Portfolio\projects\01_recommendation_service\teaching`。

第一次操作时，先读补充册第1—4章准备环境，再读主手册建立问题、数据、数学和证据之间的联系；遇到具体函数时打开代码伴读定位行号。原42页主册和35页代码伴读保持不变；再审增加29页补充册，合计106页，按问题查阅，不要求一次读完。

| 材料 | 内容与用法 |
|---|---|
| 个性化推荐与排序服务完整学习手册.docx / .pdf | 42页、23章。中文为主，保留英文技术词；含33个原生Word公式、13张图（8张真实截图、3张教学图、2张真实实验图） |
| 代码逐行阅读指南.docx / .pdf | 35页。按真实文件与行号解释模型、指标、API、网页、操作脚本、测试、复现封装和配置 |
| 代码逐行阅读指南.html | 离线单文件伴读，含29个源码/配置文件、2,185行完整代码、行号锚点、源码SHA和55个原生MathML公式 |
| 环境搭建与上游代码补充手册.docx / .pdf | 29页。现机版本、首次安装官方步骤、逐命令检查点、实际实现复杂度、2张新回放截图，以及上游Notebook逐行伴读 |
| 上游Notebook逐行伴读.html | 原SAR15与BPR11代码单元、4个辅助单元和2条缓存插入行，共255行；按单元/行号/JSON位置对应原本与执行本，含MIT归因 |
| 完整学习手册_源稿.md / equations.tex | 可继续编辑、核对的主手册与LaTeX数学来源 |
| 代码逐行阅读指南_源稿.md | 与Word/HTML一致的解释文本；完整代码由builder从项目源码读取 |
| screenshots/index.csv | 原8张截图的操作、URL、SHA256、来源、文件时间与脱敏复查；当时未记录的精确捕获时间/工具版本如实保留unknown |
| screenshots/reaudit_20261021/capture_manifest.json | 新2张真实回放截图的捕获UTC区间、动作、界面commit/模型版本、SHA、尺寸和脱敏检查 |
| qa/source_manifest.json | 伴读所用29个文件的行数与内容指纹，避免文档落后于代码 |
| notebook_sources/source_manifest.json | 26个上游原代码单元与辅助/适配代码的源码hash、位置与逐行解释覆盖 |

第一轮学习可以按这条顺序：主手册1—12章理解原理 → 第16章上游复现 → 第17—20章1M实验与部署操作 → 第15章练习 → 第21章简历和面试表达。第22章记录本次实际修复的缺陷，第23章提供术语与证据定位。第二轮只重读自己解释不清的模块，再用伴读查具体行号。

`chapters/`是主手册的分章源稿；`chapters_code_*.md`是代码伴读的解释来源。`build_manual.py`与`build_companion.py`生成DOCX/HTML；`build_assets.py`生成明确标为教学图的示意图；`export_word.ps1`用独立隐藏Word实例输出PDF；`render_pdf.py`逐页渲染供人工核验。构建需要相应Python文档依赖、本地Word和图片资产；这些脚本不重新训练模型。

补充册由`环境搭建与工具操作_源稿.md`和`上游Notebook逐行伴读_源稿.md`合成，3个新增公式源另存`supplement_equations.tex`。`build_supplement.py`继承原主册的页面与样式，保持原件不变；构建补册还需要本地原主册DOCX作为样式参考。`build_notebook_companion.py`从固定来源和可编辑说明生成Notebook伴读；首次安装说明与现机已执行检查明确分开，这次没有做干净系统重装。

公开GitHub仓库保存代码、文本源稿和汇总证据；本地DOCX/PDF、截图及逐页渲染图单独交付，未随公共仓库分发。**仅clone公开仓库不能立即完整重建主手册**：还需要这次本地截图/实验图资产以及文档运行依赖。不要将缺少图片的构建误认为模型代码运行失败。

主手册42页和伴读35页原验收见`qa/document_acceptance.json`。2026-10-21再审重新核对77张最终页及4个原Word/PDF的字节hash，并把全部正文/公式与源稿在内存重建后逐节点比较；原件未变。新增补册的逐页审查及R10—R26结果见`qa/reaudit_20261021/document_acceptance.json`和`reports/release/reaudit_20261021_teaching.json`。

两份HTML均做静态结构与来源检查；旧代码HTML的本地file导航曾被自动安全审查拒绝，没有改用其他入口绕过。因此搜索按钮和实际浏览器交互未获本次验证，不把静态检查写成交互通过。Word/PDF内容的逐页核验独立完成。历史截图的精确时间和工具build无法追溯，新回放记录不冒充旧记录。

实测范围也要保留：上游SAR/BPR八项指标与固定保存值一致；1M扩展提高长尾占比但NDCG下降；部署验证发生在本地Docker，GitHub Actions未启用。这些材料支持你独立复跑和解释，并不表示你已经完成了所有练习或拥有真实生产用户流量。
