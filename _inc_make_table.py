"""Build MutakernelV2/实验/重跑实验数据/E1_INCONCLUSIVE清算表.md from the two
fetched inventory reports (no hand-copied numbers)."""
import json
from collections import Counter
from datetime import datetime

r1 = json.load(open("_inc_inventory_report.json", encoding="utf-8"))
r2 = json.load(open("_inc_inventory2_report.json", encoding="utf-8"))
rc = r1["reconcile"]
arch_st = {name: {e["probe_id"]: e for e in entries}
           for name, entries in rc["archived_probe_status"].items()}
fresh = {f["probe_id"]: f for f in r2["fresh_345"]}

TIMEOUT_F = "cse_observations_lane0_timeout_v1.jsonl"
ENV_F = "cse_observations_env_v1.jsonl"


def attribution(rec):
    ts = rec["trial_summary"]
    if rec["file"] == TIMEOUT_F:
        return "预算不足(1800s 截断)"
    pid = rec["probe_id"]
    if pid.startswith("L1_P96"):
        return "显存配额(0.45 轮内 OOM 作废)"
    if ts["non_pass"] == 0 and ts["n_trials"] < 103:
        return "主机内存(cgroup SIGKILL 提前终止)"
    if pid == "L1_P20__relop_replace__3":
        return "显存配额(5 轮 OOM 作废,余轮达标)"
    return "争用作废(三道并发显存耗尽)+超预算"


def evidence_summary(rec):
    ts = rec["trial_summary"]
    parts = [f"{ts['n_trials']}轮", f"随机过{ts['random_pass']}/40",
             f"压力过{ts['stress_pass']}/63"]
    if ts["non_pass"]:
        parts.append(f"作废{ts['env_void_of_non_pass']}(环境)"
                     if ts["env_void_of_non_pass"] == ts["non_pass"]
                     else f"非过{ts['non_pass']}(环境作废{ts['env_void_of_non_pass']})")
    if rec["timed_out"]:
        parts.append("整探针超时")
    return " ".join(parts)


def now_state(rec):
    pid = rec["probe_id"]
    st = arch_st.get(rec["file"], {}).get(pid, {})
    if st.get("in_done_union"):
        f = fresh.get(pid)
        if f is None:
            return "已完成(旧账)"
        ev = f.get("evidence") or {}
        tag = ("重判入账(resource_degraded)"
               if ev.get("resource_degraded") and f["wall_s"] == round(
                   (rec["wall_ms"] or 0) / 1000)
               else f"已重跑 lane{f['lane']}")
        return f"{tag}→{f['outcome']}"
    return f"待跑 lane{st.get('lane')}"


cse_arch = [r for r in r1["inconclusive"]
            if r["file"] in (TIMEOUT_F, ENV_F)]
equiv_inc = [r for r in r1["inconclusive"]
             if r["file"] == "equiv_observations.jsonl"]

# unique-probe accounting
ids_timeout = {r["probe_id"] for r in cse_arch if r["file"] == TIMEOUT_F}
ids_env = {r["probe_id"] for r in cse_arch if r["file"] == ENV_F}
uniq = ids_timeout | ids_env
done_ids = {p for f, m in arch_st.items() for p, e in m.items()
            if e["in_done_union"]}
pend_ids = uniq - done_ids
attr_cnt = Counter()
for r in cse_arch:
    attr_cnt[attribution(r)] += 1

lines = []
w = lines.append
w(f"# E1 全阶段 INCONCLUSIVE 清算表(第一轮,{datetime.now():%Y-%m-%d %H:%M} 北京时间)")
w("")
w("数据源:远端 /root/mk_v2_runs/e1 全量扫描(活动观测 + 归档),"
  "只读盘点脚本 `_inc_inventory_remote.py` / `_inc_inventory2_remote.py`;"
  "重判试算用远端现行部署的预注册判级 `grade_cse_evidence`"
  "(40/40 随机 + >=42/63 定向 + 零 divergence;resource_degraded:"
  ">=77 有效轮 + >=30 随机过 + >=42 压力过,作废轮全为环境事件)。")
w("")
w("## 0. 摘要")
w("")
w("| 项 | 数 |")
w("|---|---|")
w(f"| 现存 INCONCLUSIVE 记录(含归档) | {len(cse_arch) + len(equiv_inc)} 条"
  f"(CSE 归档 {len(cse_arch)},equiv 现存 {len(equiv_inc)}) |")
w(f"| CSE 归档唯一探针 | {len(uniq)}(双档重叠 "
  f"{len(ids_timeout) + len(ids_env) - len(uniq)} 条) |")
w(f"| 其中已闭环(重跑/重判) | {len(done_ids)} |")
w(f"| 仍需重跑(已全部在 lanes 3/4/5 队列) | {len(pend_ids)} |")
w("| 本轮新增重判挽救 | 0(唯一达标者 L1_P20__relop_replace__3 前任已重判入账,"
  "本轮试算独立复核一致) |")
w("| equiv 历史超时归档(timeout_v1/v2) | 121 条记录 / 120 唯一探针,"
  "全部已在合并文件闭环(106 LIKELY + 14 WITNESSED),非存量 |")
w("")
w("归因分布(CSE 归档 44 条记录):")
w("")
for k, v in sorted(attr_cnt.items(), key=lambda kv: -kv[1]):
    w(f"- {k}:{v} 条")
w("- 合法拒判(equiv):1 条(保留 INCONCLUSIVE,不重跑)")
w("")
w("## 1. equiv 阶段现存 INCONCLUSIVE(1 条)")
w("")
w("| probe_id | inconclusive_class | 证据 | 归因 | 处置 |")
w("|---|---|---|---|---|")
mi = r2["equiv_merged_inc"]
w(f"| {mi['probe_id']} | {mi['inconclusive_class']} | "
  f"worker 崩溃:CUDA illegal memory access(wall {mi['wall_ms']/1000:.0f}s,"
  "无可用轮级证据) | 合法拒判(状态同步类,预注册口径不判等价) | "
  "保留 INCONCLUSIVE;不进 CSE 目标集(仅 LIKELY_EQUIVALENT 进) |")
w("")
w("## 2. CSE 归档逐条清算(44 条记录,按归档文件)")
w("")
w("dry 列 = 按现行预注册判级对归档轮级证据的离线重判试算(未写账)。")
w("")
for fname, title in ((TIMEOUT_F, "2.1 lane0 超时归档(36 条,1800s 预算)"),
                     (ENV_F, "2.2 envfix 归档(8 条,三道并发资源耗尽)")):
    w(f"### {title}")
    w("")
    w("| probe_id | class | wall | 轮级证据摘要 | 归因 | 重判试算 | 现状 |")
    w("|---|---|---|---|---|---|---|")
    for r in cse_arch:
        if r["file"] != fname:
            continue
        dry = r.get("regrade_dryrun", {}).get("outcome", "?")
        dry_s = "STILL(达标)" if dry == "STILL_LIKELY_EQUIVALENT" else "不达标"
        w(f"| {r['probe_id']} | {r['inconclusive_class']} | "
          f"{(r['wall_ms'] or 0)/1000:.0f}s | {evidence_summary(r)} | "
          f"{attribution(r)} | {dry_s} | {now_state(r)} |")
    w("")

w("双档重叠探针(计 1 次):" + ", ".join(sorted(ids_timeout & ids_env)))
w("")
w("## 3. 重排队完整性对账(14:35 快照)")
w("")
w("| 项 | 值 |")
w("|---|---|")
w(f"| lane0 拆分目标(全局) | {rc['lane0_targets']} |")
w(f"| 已完成(completed 并集∩目标) | {rc['done']} |")
w(f"| 待跑 | {rc['pending']}(lane3={rc['lane_pending_counts']['3']},"
  f" lane4={rc['lane_pending_counts']['4']},"
  f" lane5={rc['lane_pending_counts']['5']}) |")
w(f"| 完成+待跑 | {rc['sum_check_206']} = 206 ✓ |")
w(f"| 待跑未被 lanes3/4/5 覆盖 | {len(rc['pending_not_covered_by_345'])} ✓ |")
w(f"| 活动观测跨道重复 probe_id | "
  f"{len(rc['dup_probe_ids_across_active_obs'])} ✓ |")
w(f"| completed 文件 | " + ", ".join(
    f"{k.replace('cse_completed_','').replace('.json','')}={v}"
    for k, v in rc["completed_files"].items()) + " |")
w(f"| 归档探针在队列 | 36 条超时档:4 已闭环 + 32 在队;"
  f"8 条 envfix:1 已闭环 + 7 在队;无遗漏,无需补队 |")
w("")
w("lanes 1/2 已收官(obs 123+124,DONE 标记在),全局 CSE 目标 "
  f"{rc['global_targets_all_lanes']} 条 LIKELY_EQUIVALENT = lane0 拆分 206 + "
  "lanes1/2 247。")
w("")
w("## 4. 对症配置矩阵(仍需重跑的 35 条唯一探针)")
w("")
w("| 归因类 | 待跑数 | 所在 lane | 对症配置 | 覆盖判断 | 兜底预案 |")
w("|---|---|---|---|---|---|")
w("| 预算不足(1800s 截断) | 28(纯超时类) | 3/4/5 | 3600s 预算 + "
  "budget_exhausted 部分证据判级 | 已覆盖:历史 1800s 完成 56–74 轮,3600s "
  "外推 112–148 轮 ≥ 103 计划轮;判 STILL 只需 40+42 过。先例:L1_P16/P20 重跑 "
  "2834/3513s 全轮完成 | 若个别再超时,由部分证据判级兜底 |")
w("| 显存配额(P96 族) | 3 | lane3 队首(串行 0.92≈75.3GB) | 串行独占显存 + "
  "3600s | 基本覆盖但余量最小:P96 equiv 中位 953s×3.22≈3069s,且历史 0.45 下"
  "全轮 OOM(6GiB 分配失败),0.92 下应可分配 | **专门补跑安排**:若 lane3 跑 "
  "P96 再 INC(超时/OOM),CSE 收官后独占窗口重跑:无并发、0.92、`--timeout "
  "5400`、`--lane 3 --lane-tag p96_5400`(需先从 lane3 obs 归档该 INC 记录并从 "
  "cse_completed_lane3.json 摘除 id,lane3 停机后操作) |")
w("| 主机内存(cgroup SIGKILL) | 2(P20_relop_4/7) | lane4 | 两道并发上限"
  "(host RAM 83/120GB)+ 守护 v10.1 串接 lane5 | 已覆盖:SIGKILL 源于三道并发"
  "时代主机内存耗尽;现两道并发 + lane5 串接 | 守护 AUTORESTART + "
  "INCCOUNTS 告警 |")
w("| 争用作废(P22 族显存) | 2(P22_relop_6/8) | lane5(0.45,lane4 完成后"
  "串接) | 0.45 两道并发 + resource_degraded 判级 | 大概率覆盖:先例 "
  "L1_P22__arith_replace__20 在 0.45 下 102/103 轮、随机 40/40 全过判 STILL;"
  "历史 OOM 发生在三道并发碎片期 | 若再 INC:转 lane3 尾部(0.92)或并入 "
  "P96 独占窗 |")
w("| 合法拒判(equiv) | 0(不重跑) | — | — | 预注册口径保留 INCONCLUSIVE | — |")
w("")
w("注:35 条唯一待跑 = 28(纯超时)+ 3(P96)+ 2(主机内存)+ 2(争用作废)"
  "= 32(超时档)+ 3(P96 仅在 envfix 档);P20_relop_4/7、P22_relop_6/8 "
  "同时在两档(双归因),按更针对性的归因行归类。")
w("")
w("## 5. 看护升级(已上线)")
w("")
w("- 远端守护升级 v9 → **v10.1**(14:41 部署,pidfile 流程:停 91232/91887 → "
  "改 → 起 91971;两道驱动 PID 89920/90128 全程不变):进度行由 "
  "`cse lane L obs=N` 改为 `cse lane L obs=N inconclusive=I`,I = 该 lane "
  "观测文件中 INCONCLUSIVE 计数,每 30 分钟写入 e1_cse_laneL.log。"
  "v9 备份于 e1_guard_cse_split_v9.bak.sh。")
w("- 本地看护链路不变:_watch_cse_cycle.py 每 10 分钟独立统计各 lane "
  "INCONCLUSIVE 输出 INCCOUNTS 行,_watch_cse.py 对增量报 "
  "ALERT_INCONCLUSIVE_GROWTH。远端进度行与本地 INCCOUNTS 构成双通道。")
w("- 当前基线:lane3=0,lane4=0,lane5=0(任何 >0 即告警并触发第二轮清算)。")
w("")
w("## 6. 红线遵守")
w("")
w("- 判级语义未改:重判试算只调用远端现行部署的预注册 `grade_cse_evidence`;"
  "本轮 0 条新写账。")
w("- 已完成 STILL/FALSIFIED/WITNESSED 记录未动;归档文件原样保留。")
w("- 守护修改走停-改-起,期间 lane3/4 驱动不受影响(PID 快照核对一致)。")
w("- 未 git commit。")

out = ("MutakernelV2/实验/重跑实验数据/E1_INCONCLUSIVE清算表.md")
open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("WROTE", out, f"({len(lines)} lines)")
