"""Generate the dual-review worklist for the 50 new L3 contract drafts."""
import io
import json
from pathlib import Path

TABLE = Path("_l3_scope_task_table.json")
OUT = Path("MutakernelV2/实验/补充实验数据/E3_L3契约草稿待审清单.md")

table = json.loads(TABLE.read_text(encoding="utf-8"))
l3 = [t for t in table["tasks"] if t["level"] == 3]
l3.sort(key=lambda t: int(t["task_key"].split("_P")[1]))

UNRESOLVED = {"L3_P29", "L3_P30"}

lines = [
    "# L3 契约草稿待审清单（50 条）",
    "",
    "生成于 2026-07-30，来源 `l3_scope/task_table.json`"
    "（契约批次 `contracts_c2c3c5_draft_l3.jsonl`，",
    "`batch_sha256 ad6f12c8…17cf`）。**本清单只做审核准备，未做任何审核。**",
    "",
    "## 审核要点（每条草稿三项人工条款 + 两项 L3 专有检查）",
    "",
    "提取器对全部 250 条草稿写入的默认值都是保守占位，`notes` 字段已标记待审。"
    "三项通用人工条款：",
    "",
    "1. **`value_domain`**：默认 `unrestricted_finite`。L3 是整网/整层模型，需逐条判断"
    "输入是否有隐含定义域（如归一化层前的取值范围、注意力 mask 的取值集合、"
    "RNN 初始隐状态的合法范围）。放宽过度会把合法失败判成缺陷，收紧过度会漏掉真缺陷；",
    "2. **变维（variable dimensions）**：默认冻结为 `get_inputs()` 观测到的形状。"
    "L3 里 batch、序列长度、图像边长通常是可变维，需明确哪些维度允许变化、"
    "变化后契约是否仍成立（这直接决定压力策略能否改形状）；",
    "3. **`deterministic`**：默认 `True`。**L3 的最高风险项**——含 dropout、"
    "随机深度（stochastic depth）、`cudnn` 非确定性卷积/RNN 反向的模型，在 eval 模式下"
    "通常确定，但需逐条确认；若不确定，必须改为 `False` 并说明，否则会把非确定性"
    "抖动记成缺陷。",
    "",
    "两项 L3 专有检查：",
    "",
    "4. **输出结构**：确认模型输出是单张量还是容器。meta 传播显示 48/50 为单张量，"
    "但这是形状层面的判断；若实跑发现容器输出，该 (subject, dtype) 落在 B9 port 的"
    "单张量域之外，按既定口径**计入分母、不计检出**，不得静默排除；",
    "5. **状态同步**：L3 模型带大量 buffer（BatchNorm 的 running stats 等）。"
    "确认 `compare_module_state` 与按名状态同步在该模型上成立——E0 的两个完备性缺口"
    "之一正是严格按名状态同步会拒绝键名不一致的候选。",
    "",
    "## 待审清单",
    "",
    "| # | task_id | 任务文件 | dtypes | 归约类 | 静态尺寸 | 备注 |",
    "|--:|---------|---------|--------|:-----:|---------|------|",
]

for index, task in enumerate(l3, 1):
    key = task["task_key"]
    name = Path(task["file"]).name
    dtypes = "/".join(d.replace("float", "f") for d in task["dtypes"])
    heavy = "是" if task["reduction_heavy"] else "—"
    if key in UNRESOLVED:
        size = "**未解析**"
        note = "meta 无法传播（数据相关形状），需一次真实前向取输出形状"
    else:
        size = "meta 已解析"
        note = ""
    lines.append("| %d | `%s` | `%s` | %s | %s | %s | %s |"
                 % (index, key, name, dtypes, heavy, size, note))

lines += [
    "",
    "## 统计",
    "",
    "| 项 | 值 |",
    "|----|----|",
    "| 待审草稿 | **%d** |" % len(l3),
    "| 归约类（策略排序用，不影响判定） | %d |"
    % sum(1 for t in l3 if t["reduction_heavy"]),
    "| dtypes 为 fp32+fp16 | %d |" % sum(1 for t in l3 if len(t["dtypes"]) == 2),
    "| 静态尺寸未解析（需真实前向） | %d（`%s`） |"
    % (len(UNRESOLVED), "`、`".join(sorted(UNRESOLVED))),
    "| 预估审核工时 | 约 8 人时（50 × 5 min × 2 审核者） |",
    "",
    "## 冻结前置条件",
    "",
    "- 三项人工条款逐条判定并留痕（判定人、日期、依据）；",
    "- 任何条款改动必须 bump `contract_id` 后缀并记录原因（契约治理要求）；",
    "- 审核必须在**该语料的任何观测落盘之前**完成（观测前冻结）；",
    "- 冻结后复核 200 条既有 `contract_sha256` 是否仍未变动，并记录新的"
    " `batch_sha256`。",
    "",
]

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote %s (%d lines, %d L3 tasks)" % (OUT, len(lines), len(l3)))
print("reduction_heavy: %d ; both dtypes: %d"
      % (sum(1 for t in l3 if t["reduction_heavy"]),
         sum(1 for t in l3 if len(t["dtypes"]) == 2)))
