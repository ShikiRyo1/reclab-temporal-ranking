"""Build source-linked teaching for all original and injected Notebook code.

Reads the pinned notebooks and local executed copies, but exports no outputs.
The editable notes are notebook_annotations.json; this script checks coverage.
"""
from pathlib import Path
import datetime
import hashlib
import html
import json
import re
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = ROOT.parents[1]
UPSTREAM = WORK / "external/recommenders"
PIN = "aa8332189cd495be6ffaa7e1c8054f1c180b5ef3"
PATHS = {
    "sar": "examples/00_quick_start/sar_movielens.ipynb",
    "bpr": "examples/02_model_collaborative_filtering/cornac_bpr_deep_dive.ipynb",
}
SOURCES = HERE / "notebook_sources"
SOURCES.mkdir(exist_ok=True)
FENCE = chr(96) * 3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(cell):
    value = cell["source"]
    return "".join(value) if isinstance(value, list) else value


def json_lines(path):
    """Map each true source line to its physical JSON line in these exact files."""
    raw = path.read_text(encoding="utf-8").splitlines()
    starts = [i for i, line in enumerate(raw) if re.match(r'\s*"cell_type":', line)]
    answer = {}
    for cell, start in enumerate(starts, 1):
        stop = starts[cell] if cell < len(starts) else len(raw)
        source = next(i for i in range(start, stop) if re.match(r'\s*"source": \[', raw[i]))
        decoded, positions = [], []
        for index in range(source + 1, stop):
            line = raw[index].strip()
            if line.startswith("]"):
                break
            value = json.loads(line.rstrip(","))
            decoded.append(value)
            positions.extend([index + 1] * len(value.splitlines()))
        answer[cell] = {"text": "".join(decoded), "lines": positions}
    return answer


def notes_for(source_lines, notes):
    mapping = {}
    for note in notes:
        for line in range(note["start"], note["end"] + 1):
            if line in mapping:
                raise ValueError(f"Overlapping annotations at {line}")
            mapping[line] = note["text"]
    for line, code in enumerate(source_lines, 1):
        if line not in mapping:
            if code.strip():
                raise ValueError(f"Missing explanation at L{line}: {code}")
            mapping[line] = "空行：分隔相邻逻辑，不执行操作。"
    if set(mapping) != set(range(1, len(source_lines) + 1)):
        raise ValueError("Annotations extend beyond the code cell")
    return mapping


INTRO = r"""# 上游 Notebook 逐行伴读

## 固定源码复现：从每一行到可核查的结果

本部分补齐官方 SAR 与 BPR Notebook 的所有可执行代码，不要求你一次背完。读完后应能指出每个输入从哪里来、模型在哪一行训练、哪个量只用于显示，以及为什么两个原版结果不能直接比较。先按 SAR 从读表走到评价，再用 BPR 对照切分和标签的差别。环境安装与 Notebook 的启动步骤放在本补充手册前半部。

来源固定为 Recommenders 提交 aa8332189cd495be6ffaa7e1c8054f1c180b5ef3，许可证为 MIT，版权归 Recommenders contributors。原代码保持原样；中文说明和复现辅助单元由本项目补充。完整许可证位于 baseline/UPSTREAM_LICENSE，也复制到 teaching/notebook_sources/UPSTREAM_LICENSE。未刊载 MovieLens 原始行、逐用户评分或推荐输出。

原单元和执行单元都从 1 开始计数，Markdown 单元也计入；它们与左侧 In [数字] 的执行次序不同。L1 表示该代码单元内部第一行。执行本在最前加了一个辅助单元，所以原单元 c 对应执行单元 c+1。只有两个读表单元额外插入缓存参数，后续行号因此再加 1。

原源码本地根目录为 H:\Career_AI_Portfolio\external\recommenders；SAR 文件为 examples/00_quick_start/sar_movielens.ipynb，BPR 文件为 examples/02_model_collaborative_filtering/cornac_bpr_deep_dive.ipynb。已运行副本在项目 reports/baseline/sar_executed.ipynb 与 bpr_executed.ipynb。HTML 逐行表附原文件 JSON 实体行、单元行、执行本行；完整 SHA-256 与覆盖清单在 teaching/notebook_sources/source_manifest.json。屏幕自动折行不会改变 L 编号。

阅读用源代码导出到 teaching/notebook_sources/*_code.txt，带单元边界但不含执行输出。含百分号魔法命令的片段应在 Notebook 运行，不能直接当普通 Python 文件执行。需要重跑时使用 baseline/run_upstream.py，它会刷新原执行报告；本次补充教案没有重训练或覆盖冻结结果。
"""

FORMULAS = r"""
这里用 h_r 表示第 r 个推荐是否命中（0 或 1），R_u 是用户 u 在原测试表中的物品集合。Precision@r 是截至 r 的命中比例。下式是本固定版本 map_at_k 的分母：

$$AP@K=\frac{\sum_{r=1}^{K}h_r\,Precision@r}{\min(K,|R_u|)}$$

再对评估用户取平均得到 MAP。Precision@K 的分母是 K；Recall@K 的分母是该用户全部真值物品数量。NDCG 把命中折扣之和除以同一用户的理想折扣之和：

$$NDCG@K=\frac{\sum_{r=1}^{K}h_r/\log(1+r)}{\sum_{r=1}^{\min(K,|R_u|)}1/\log(1+r)}$$

教学手算：K=3，真值有 2 个物品，推荐命中序列为 [1,0,1]。Precision=2/3，Recall=1，AP=(1+2/3)/2=5/6；NDCG=(1+1/2)/(1+1/log2(3))≈0.9197。这里是自造小例子，不是用户 54 的真实结果。
"""

RATING_NOTE = r"""
用 y 表示交集中的真实评分，ŷ 表示对应 prediction，n 为交集行数，则 RMSE 是平方误差平均后开根号，MAE 是绝对误差的平均。不要因 normalize=True 就把 SAR 视为专业评分回归器：原项目也说明它主要面向排序。

$$RMSE=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat y_i)^2},\qquad MAE=\frac{1}{n}\sum_{i=1}^{n}|y_i-\hat y_i|$$

logloss 的 y 改成 0/1、p 改成缩放值后，单行损失为 −y log(p)−(1−y)log(1−p)。库对数值端点有处理，不能手工把 log(0) 当成项目真实输出。本例只示范调用；未经校准、且只在推荐与真值交集上评价，不能据此得出整体点击概率质量。
"""

END = r"""
### 两个缓存参数与四个辅助单元

执行副本对 SAR 原单元 8 与 BPR 原单元 9 做同一种插入：在调用 load_pandas_df 的第一行之后增加 local_cache_path。这把下载与缓存定位到 H 盘，不改变 zip 字节、标签、切分参数或算法。原 L1 仍是执行 L1，新增缓存行为执行 L2，原 L2 及以后对应执行 L3 及以后；两个单元的每行映射都写入 manifest。

其余新增代码是各执行本首尾的两个辅助单元。下面完整解释这四个单元；它们的代码来自本项目，不属于上游原单元。先看导入路径，再看证据导出，便能分清“模型本身”和“怎样证明模型跑过”。
"""

OUTRO = r"""
### 实测结果与练习核对

| 原版实验 | MAP@10 | NDCG@10 | Precision@10 | Recall@10 |
|---|---:|---:|---:|---:|
| SAR 100K | 0.2447220531 | 0.3795334515 | 0.3310710498 | 0.1768368472 |
| BPR 100K | 0.1803676443 | 0.3051899537 | 0.2390322581 | 0.2086604438 |

每个实测值与自己固定 Notebook 的保存值逐项相同。SAR 用全评分与每用户随机切分，BPR 用评分>3.5 的正反馈与全表随机切分，所以表格只核对复现，不给算法排优劣。README 总表曾列出另一组 SAR NDCG 0.3938；验收依据是本固定 Notebook 的 0.3795334515，不能把总表数字移过来冒充同协议结果。

独立 1M 时间实验另外定义训练目录、可达目标、冷用户与验证选参。不要把上游随机切分的分数与它的时间测试分数拼成“提升曲线”。原 BPR Markdown 展示的梯度符号存在问题，已经保留原文并在主手册解释：实际 Cornac 2.3.0 更新使用正确的似然与负正则项，有限差分核验另见 reports/baseline/bpr_gradient_check.json。忠实执行代码不等于认可原说明里的每个公式。

自检 1：SAR 中把 positivity_threshold 改成 3.5，会改变前面的四项排序结果吗？答案：在这份顺序里不会；它只改 logloss 演示副本，前面的排序使用原 test。自检 2：BPR 的 TOP_K=10 为什么还生成一百多万行预测？答案：模型调用省略 top_k，包装方法默认返回所有未见候选；评估器才截前 10。自检 3：用户 54 合并表里 NaN 是预测 0 分吗？答案：不是，它表示左表该真值键没有匹配到本次推荐表。

完成这些辨析后，再回到自己的 1M 代码伴读：检查候选与 seen 过滤、验证选参和服务快照的边界。你应能从一个结果追溯到数据、具体单元和实际行号；仅能复述最终指标还不足以说明你能独立维护项目。
"""


def helper_notes(model, which, lines):
    if which == "preamble":
        return [
            {"start": 1, "end": 1, "text": "导入 sys，准备调整此内核进程的模块搜索顺序。"},
            {"start": 2, "end": 2, "text": "把固定源码 checkout 插到 sys.path 第 0 位，保证 import recommenders 读取本次核验过的目录，不是机器上的另一个安装版本。Windows 路径中的双反斜杠是字符串转义。"},
            {"start": 3, "end": 3, "text": "打印预期固定提交，帮助阅读输出。打印本身不能证明磁盘确实在该提交；runner 在执行前另用 git rev-parse 与 git diff 进行真实检查。"},
        ]
    notes = [
        (1, 2, "L1 导入 JSON 与 SHA-256 工具；L2 导入 Path 用于文件写入。它们不参与模型打分。"),
        (3, 4, "L3 定义 frame_hash；L4 把表按当前行序导出为不含索引、换行固定为 \\n 的 CSV 字节，再计算 SHA-256。这里保存的是摘要，不把评分表写成公共文件。"),
        (5, 6, "L5 开始 evidence 字典；L6 保存训练与测试的行数。变量 train/test 已由原单元创建。"),
        (7, 8, "L7 保存去重用户数，L8 保存去重物品数；int 将 NumPy 计数转成可直接 JSON 序列化的 Python 整数。"),
        (9, 10, "L9 对训练/测试用户集合取交集，L10 取测试减训练的差集，分别记录共同用户与只在测试出现的用户数量。"),
        (11, 11, "isin 判断测试物品是否存在于训练物品中，~ 取反，sum 计数；这是训练目录外测试行数量，不是测试冷用户数。"),
        (12, 13, "L12 记录训练/测试表哈希；L13 保存当前 data 行数和 seed=42。" + ("SAR 的 data 仍为原始 100,000 行，没有先按评分阈值过滤。" if model == "sar" else "BPR 的 data 已经过正反馈过滤，实际为 55,375 行。") + "seed 字段是已核实的参数记录，不在此重设随机数。"),
        (14, 16, "L14/15 保存四项已算出的排序指标，float 兼容 JSON 数值；L16 关闭字典。不会把指标重新算一次。"),
    ]
    if model == "sar":
        notes.extend([
            (17, 17, "用字典推导式逐项保存 RMSE、MAE、R²、解释方差和 logloss，所有值转成 float；这些是原单元实际运行结果。"),
            (18, 19, "L18/19 分别保存训练和预测计时器的 interval。计时不同不等于排序复现失败。"),
            (20, 20, "记录 top_k 表行数，用于核对用户数乘推荐长度。"),
            (21, 22, "L21 以 UTF-8 将 details 格式化写入 sar_run_details.json；L22 在 Notebook 再显示字典。只有汇总数量、指标与哈希，不包含逐用户评分。"),
        ])
    else:
        notes.extend([
            (17, 17, "记录 all_predictions 的行数；没有把所有预测明细写入 JSON。"),
            (18, 19, "L18 写入 bpr_run_details.json，indent=2 方便阅读；L19 显示汇总字典。BPR 原计时变量 t 被复用，所以此单元没有仿造不存在的独立训练时间字段。"),
        ])
    return [{"start": a, "end": b, "text": t} for a, b, t in notes]


def main():
    annotations = json.loads((HERE / "notebook_annotations.json").read_text(encoding="utf-8"))
    note_map = {(x["model"], x["original_cell_1based"]): x for x in annotations["cells"]}
    manifest = {"version": 1, "built_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "commit": PIN, "license": "MIT", "copyright": "Recommenders contributors",
                "scope": "All original code, two local cache insertions and four helper cells; no execution outputs redistributed.",
                "notebooks": [], "cells": []}
    md = [INTRO]
    html_sections = []
    raw_files = {}
    all_records = []
    pairs = {}
    for model, relative in PATHS.items():
        source = UPSTREAM / relative
        executed = ROOT / f"reports/baseline/{model}_executed.ipynb"
        original = json.loads(source.read_text(encoding="utf-8"))
        run = json.loads(executed.read_text(encoding="utf-8"))
        original_json, executed_json = json_lines(source), json_lines(executed)
        pairs[model] = (original, run, original_json, executed_json)
        manifest["notebooks"].append({
            "model": model, "upstream_file": relative, "source_sha256": sha(source),
            "source_local_path": str(source), "executed_local_path": str(executed),
            "executed_sha256": sha(executed),
            "url": f"https://github.com/recommenders-team/recommenders/blob/{PIN}/{relative}",
        })
        export = [f"# Copyright (c) Recommenders contributors. MIT License; commit {PIN}.",
                  "# Reading export only: use the Notebook kernel for IPython magic commands.", ""]
        for original_index, cell in enumerate(original["cells"], 1):
            if cell["cell_type"] != "code":
                continue
            guide = note_map[(model, original_index)]
            lines = text(cell).splitlines()
            mapping = notes_for(lines, guide["notes"])
            actual_cell = run["cells"][original_index]
            expected = text(cell).replace("data = movielens.load_pandas_df(",
                       f"data = movielens.load_pandas_df(\n    local_cache_path={str(WORK / 'data/movielens')!r},")
            assert text(actual_cell) == expected
            assert original_json[original_index]["text"] == text(cell)
            assert executed_json[original_index + 1]["text"] == text(actual_cell)
            cache = int("data = movielens.load_pandas_df(" in text(cell))
            export.extend([f"# {model.upper()} original cell {original_index}; executed cell {original_index+1}", ""])
            export_start = len(export) + 1
            export.extend(lines + [""])
            record = {"id": f"{model}-original-{original_index}", "model": model, "kind": "upstream_original",
                      "original_cell_1based": original_index, "executed_cell_1based": original_index + 1,
                      "title": guide["title"], "context": guide["context"],
                      "source_cell_sha256": hashlib.sha256(text(cell).encode()).hexdigest(),
                      "lines": len(lines), "annotations": guide["notes"],
                      "line_mapping": [
                          {"source_line": n, "source_json_line": original_json[original_index]["lines"][n-1],
                           "executed_line": n + (1 if cache and n >= 2 else 0),
                           "executed_json_line": executed_json[original_index+1]["lines"][n-1+(1 if cache and n>=2 else 0)],
                           "export_line": export_start+n-1, "explanation": mapping[n]}
                          for n in range(1, len(lines)+1)],
                      "cache_parameter_inserted": bool(cache), "covered_lines": len(mapping)}
            if cache:
                record["inserted_line"] = {"executed_line": 2, "source": text(actual_cell).splitlines()[1],
                    "executed_json_line": executed_json[original_index+1]["lines"][1],
                    "explanation": "指定固定本地缓存目录；读取已做 SHA-256 核验的同一 MovieLens 压缩包内容。"}
            all_records.append((record, lines, mapping, guide["notes"]))
        raw_files[model] = export
    for record, lines, mapping, notes in all_records:
        manifest["cells"].append(record)
        add_section(md, html_sections, record, lines, mapping, notes)
        if record["model"] == "sar" and record["original_cell_1based"] == 20:
            md.append(FORMULAS)
        if record["model"] == "sar" and record["original_cell_1based"] == 22:
            md.append(RATING_NOTE)
    md.append(END)
    for model, (original, run, original_json, executed_json) in pairs.items():
        for which, index in (("preamble", 1), ("capture", len(run["cells"]))):
            cell = run["cells"][index-1]
            lines = text(cell).splitlines()
            notes = helper_notes(model, which, lines)
            mapping = notes_for(lines, notes)
            record = {"id": f"{model}-helper-{which}", "model": model, "kind": "local_helper",
                      "original_cell_1based": None, "executed_cell_1based": index,
                      "title": "固定源码导入路径" if which == "preamble" else "导出本次执行证据",
                      "context": "此单元来自本项目的 run_upstream.py，不是上游算法改写。",
                      "source_cell_sha256": hashlib.sha256(text(cell).encode()).hexdigest(),
                      "lines": len(lines), "annotations": notes, "covered_lines": len(mapping),
                      "line_mapping": [{"source_line": n, "executed_line": n,
                                        "executed_json_line": executed_json[index]["lines"][n-1],
                                        "explanation": mapping[n]} for n in range(1, len(lines)+1)]}
            manifest["cells"].append(record)
            add_section(md, html_sections, record, lines, mapping, notes)
            raw_files[model].extend([f"# Local helper {which}; executed cell {index}", *lines, ""])
    md.append(OUTRO)
    source_md = "\n\n".join(md)
    (HERE / "上游Notebook逐行伴读_源稿.md").write_text(source_md, encoding="utf-8")
    for model, lines in raw_files.items():
        (SOURCES / f"{model}_code.txt").write_text("\n".join(lines), encoding="utf-8")
    shutil.copyfile(ROOT / "baseline/UPSTREAM_LICENSE", SOURCES / "UPSTREAM_LICENSE")
    manifest["totals"] = {
        "original_code_cells": sum(x["kind"] == "upstream_original" for x in manifest["cells"]),
        "original_code_lines_including_blank_and_comment": sum(x["lines"] for x in manifest["cells"] if x["kind"] == "upstream_original"),
        "helper_code_cells": sum(x["kind"] == "local_helper" for x in manifest["cells"]),
        "helper_code_lines": sum(x["lines"] for x in manifest["cells"] if x["kind"] == "local_helper"),
        "cache_parameter_lines": sum(bool(x.get("cache_parameter_inserted")) for x in manifest["cells"]),
        "unexplained_lines": sum(x["lines"]-x["covered_lines"] for x in manifest["cells"]),
    }
    manifest["generated_files"] = {p.name: sha(p) for p in [HERE / "上游Notebook逐行伴读_源稿.md",
        HERE / "notebook_annotations.json", *sorted(SOURCES.glob("*_code.txt")), SOURCES / "UPSTREAM_LICENSE"]}
    css = """body{font:16px/1.7 'Microsoft YaHei',sans-serif;background:#fff;color:#18232f;margin:0}
main{max-width:1200px;margin:auto;padding:30px}h1,h2,h3{line-height:1.4}h2{margin-top:45px}
nav{position:sticky;top:0;background:#edf3f7;padding:12px;z-index:1}nav a{margin-right:18px}
table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #d6dde3;padding:8px;vertical-align:top}
.line{width:65px}.code{width:48%}pre{font:13px/1.5 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}
.origin{font-size:13px;color:#425366;overflow-wrap:anywhere}.note{font-size:14px}tr:nth-child(even){background:#f5f7f9}
@media(max-width:800px){main{padding:12px}.code{width:42%}.note{font-size:12px}pre{font-size:11px}}"""
    toc = "".join(f'<li><a href="#{x["id"]}">{x["model"].upper()} '
                  f'{"原单元 "+str(x["original_cell_1based"]) if x["kind"]=="upstream_original" else "辅助单元 "+str(x["executed_cell_1based"])}'
                  f'：{html.escape(x["title"])}</a></li>' for x in manifest["cells"])
    page = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page += "<title>上游 Notebook 逐行代码与解释</title><style>"+css+"</style></head><body>"
    page += '<nav><a href="#index">单元目录</a><a href="notebook_sources/source_manifest.json">完整来源与覆盖清单</a>'
    page += '<a href="notebook_sources/UPSTREAM_LICENSE">MIT 许可证</a></nav><main id="index">'
    page += "<h1>上游 Notebook 逐行代码与解释</h1><p>固定提交："+PIN+"</p>"
    page += "<p>原单元与执行单元均从 1 开始、含 Markdown 单元；L 为单元内部实际行号。每行附原 JSON 行与执行本行。此网页只提供源码及教学说明，不含 MovieLens 逐用户输出。完整数学与练习见同名源稿及环境搭建与上游代码补充手册。</p>"
    page += "<p>原代码版权归 Recommenders contributors（MIT）；本项目添加中文说明、缓存路径及四个辅助单元。浏览器 Ctrl+F 可查关键字。</p><ol>"+toc+"</ol>"
    page += "".join(html_sections)+"</main></body></html>"
    output_html = HERE / "上游Notebook逐行伴读.html"
    output_html.write_text(page, encoding="utf-8")
    manifest["generated_files"][output_html.name] = sha(output_html)
    (SOURCES / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(manifest["totals"], ensure_ascii=False))


def add_section(md, html_sections, record, lines, mapping, notes):
    model = record["model"].upper()
    origin = ("原单元 " + str(record["original_cell_1based"])) if record["kind"] == "upstream_original" else "本地辅助单元"
    heading = f'{model} {origin}：{record["title"]}'
    location = f'{origin} → 执行单元 {record["executed_cell_1based"]}；L1–L{len(lines)}；单元源码 SHA-256 前 12 位 {record["source_cell_sha256"][:12]}。'
    md.extend(["### "+heading, location, record["context"]])
    # The unchanged code remains copyable; labels mark original cell line ranges.
    for start in range(0, len(lines), 15):
        end = min(start+15, len(lines))
        if len(lines) > 15:
            md.append(f"代码 L{start+1}–L{end}（同一单元的连续片段）：")
        md.append(FENCE+"python\n"+"\n".join(lines[start:end])+"\n"+FENCE)
    for note in notes:
        label = f'L{note["start"]}' if note["start"] == note["end"] else f'L{note["start"]}–L{note["end"]}'
        md.append(label+"："+note["text"])
    blank = [str(n) for n, line in enumerate(lines, 1) if not line.strip() and not any(x["start"]<=n<=x["end"] for x in notes)]
    if blank:
        md.append("空行 L"+"/L".join(blank)+" 仅分隔逻辑，不执行操作。")
    if record.get("cache_parameter_inserted"):
        md.append("执行副本新增的 L2 是：")
        md.append(FENCE+"python\n"+record["inserted_line"]["source"]+"\n"+FENCE)
        md.append("该行固定 H 盘缓存位置；原 L2 及之后的内容保持原样，映射到执行本时行号加 1。")
    section = '<section id="'+record["id"]+'"><h2>'+html.escape(heading)+'</h2><p class="origin">'+html.escape(location)
    section += '</p><p>'+html.escape(record["context"])+'</p><table><thead><tr><th class="line">单元行</th><th class="code">原代码</th><th>说明与真实位置</th></tr></thead><tbody>'
    for line, code in enumerate(lines, 1):
        ref = record["line_mapping"][line-1]
        physical = "执行 JSON L"+str(ref["executed_json_line"])+f'；执行单元 L{ref["executed_line"]}'
        if "source_json_line" in ref:
            physical = "原 JSON L"+str(ref["source_json_line"])+"；"+physical
        section += f'<tr id="{record["id"]}-L{line}"><td class="line">L{line}</td><td class="code"><pre>{html.escape(code)}</pre></td>'
        section += '<td class="note">'+html.escape(mapping[line])+'<div class="origin">'+physical+'</div></td></tr>'
    section += "</tbody></table>"
    if record.get("cache_parameter_inserted"):
        section += '<p>执行副本新增 L2（其余行对应顺延）：</p><pre>'+html.escape(record["inserted_line"]["source"])+"</pre>"
    html_sections.append(section+"</section>")


if __name__ == "__main__":
    main()
