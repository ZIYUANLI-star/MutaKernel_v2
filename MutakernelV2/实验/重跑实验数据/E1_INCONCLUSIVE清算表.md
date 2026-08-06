# E1 全阶段 INCONCLUSIVE 清算表(第一轮,2026-07-27 14:44 北京时间)

## 终版归类规则(2026-07-27 15:10 增补,导师确认口径)

1. 补跑后得到有效判级的探针,其实验数据**归入对应判级类别**(LIKELY / WITNESSED / FALSIFIED 等),中间态 INCONCLUSIVE 记录仅归档留痕,不进入任何最终统计;
2. 只有**穷尽对症补跑配置后仍无法定级**的探针才计入终版 INCONCLUSIVE(蓝图 Table 10 的 INCONCLUSIVE 列语义 = 盲审后仍无法定级,与此一致);
3. 任何"归因为环境/资源/预算"的 INCONCLUSIVE 都不允许直接进入终版——必须至少经历一次对症配置的重试;只有归因为"结构性不可判"(如状态同步非双射)或"重试后确定性复现且严格 Oracle 仍无法健全定级"的才算穷尽。

数据源:远端 /root/mk_v2_runs/e1 全量扫描(活动观测 + 归档),只读盘点脚本 `_inc_inventory_remote.py` / `_inc_inventory2_remote.py`;重判试算用远端现行部署的预注册判级 `grade_cse_evidence`(40/40 随机 + >=42/63 定向 + 零 divergence;resource_degraded:>=77 有效轮 + >=30 随机过 + >=42 压力过,作废轮全为环境事件)。

## 0. 摘要

| 项 | 数 |
|---|---|
| 现存 INCONCLUSIVE 记录(含归档) | 45 条(CSE 归档 44,equiv 现存 1) |
| CSE 归档唯一探针 | 39(双档重叠 5 条) |
| 其中已闭环(重跑/重判) | 4 |
| 仍需重跑(已全部在 lanes 3/4/5 队列) | 35 |
| 本轮新增重判挽救 | 0(唯一达标者 L1_P20__relop_replace__3 前任已重判入账,本轮试算独立复核一致) |
| equiv 历史超时归档(timeout_v1/v2) | 121 条记录 / 120 唯一探针,全部已在合并文件闭环(106 LIKELY + 14 WITNESSED),非存量 |

归因分布(CSE 归档 44 条记录):

- 预算不足(1800s 截断):36 条
- 显存配额(0.45 轮内 OOM 作废):3 条
- 主机内存(cgroup SIGKILL 提前终止):2 条
- 争用作废(三道并发显存耗尽)+超预算:2 条
- 显存配额(5 轮 OOM 作废,余轮达标):1 条
- 合法拒判(equiv):1 条(保留 INCONCLUSIVE,不重跑)

## 1. equiv 阶段现存 INCONCLUSIVE(1 条)

| probe_id | inconclusive_class | 证据 | 归因 | 处置 |
|---|---|---|---|---|
| L1_P95__relop_replace__5 | other_unknown | worker 崩溃:CUDA illegal memory access(wall 61s,无可用轮级证据) | 待定:崩溃可能是变异体真实缺陷(越界访问),也可能是环境瞬态 | **按终版归类规则改为重试**:CSE 收官后独占窗口重跑一次;若确定性复现且参考端健康,按严格 Oracle 判 SPEC_VIOLATION 归入实锤非等价;若瞬态消失则正常判级;两次重试后仍无法定级才计终版 INCONCLUSIVE |

## 2. CSE 归档逐条清算(44 条记录,按归档文件)

dry 列 = 按现行预注册判级对归档轮级证据的离线重判试算(未写账)。

### 2.1 lane0 超时归档(36 条,1800s 预算)

| probe_id | class | wall | 轮级证据摘要 | 归因 | 重判试算 | 现状 |
|---|---|---|---|---|---|---|
| L1_P16__arith_replace__6 | timeout | 1800s | 60轮 随机过40/40 压力过20/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 已重跑 lane3→STILL_LIKELY_EQUIVALENT |
| L1_P19__arith_replace__3 | timeout | 1803s | 58轮 随机过40/40 压力过18/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane3 |
| L1_P19__relop_replace__1 | timeout | 1803s | 59轮 随机过40/40 压力过19/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane3 |
| L1_P20__arith_replace__18 | timeout | 1802s | 60轮 随机过40/40 压力过20/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 已重跑 lane4→STILL_LIKELY_EQUIVALENT |
| L1_P20__relop_replace__3 | timeout | 1802s | 59轮 随机过40/40 压力过19/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 已重跑 lane4→STILL_LIKELY_EQUIVALENT |
| L1_P20__relop_replace__7 | timeout | 1801s | 56轮 随机过40/40 压力过16/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P20__relop_replace__4 | timeout | 1806s | 58轮 随机过40/40 压力过18/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P20__const_perturb__11 | timeout | 1802s | 58轮 随机过40/40 压力过18/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P20__mask_boundary__0 | timeout | 1802s | 59轮 随机过40/40 压力过19/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P21__relop_replace__3 | timeout | 1803s | 59轮 随机过40/40 压力过19/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane3 |
| L1_P21__relop_replace__0 | timeout | 1803s | 60轮 随机过40/40 压力过20/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane3 |
| L1_P21__relop_replace__5 | timeout | 1803s | 60轮 随机过40/40 压力过20/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane3 |
| L1_P21__const_perturb__2 | timeout | 1802s | 59轮 随机过40/40 压力过19/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane3 |
| L1_P21__mask_boundary__0 | timeout | 1801s | 58轮 随机过40/40 压力过18/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane3 |
| L1_P22__arith_replace__20 | timeout | 1801s | 69轮 随机过40/40 压力过29/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 已重跑 lane5→STILL_LIKELY_EQUIVALENT |
| L1_P22__relop_replace__6 | timeout | 1802s | 72轮 随机过40/40 压力过32/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P22__relop_replace__8 | timeout | 1802s | 73轮 随机过40/40 压力过33/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P22__const_perturb__21 | timeout | 1801s | 73轮 随机过40/40 压力过33/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P22__const_perturb__0 | timeout | 1802s | 74轮 随机过40/40 压力过34/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P22__const_perturb__6 | timeout | 1801s | 74轮 随机过40/40 压力过34/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P22__index_replace__10 | timeout | 1802s | 72轮 随机过40/40 压力过32/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P22__mask_boundary__0 | timeout | 1801s | 72轮 随机过40/40 压力过32/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P22__mask_boundary__1 | timeout | 1801s | 73轮 随机过40/40 压力过33/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__const_perturb__3 | timeout | 1802s | 73轮 随机过40/40 压力过33/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__const_perturb__2 | timeout | 1802s | 74轮 随机过40/40 压力过34/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__const_perturb__1 | timeout | 1801s | 72轮 随机过40/40 压力过32/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__index_replace__6 | timeout | 1802s | 74轮 随机过40/40 压力过34/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__mask_boundary__0 | timeout | 1801s | 71轮 随机过40/40 压力过31/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__mask_boundary__1 | timeout | 1802s | 74轮 随机过40/40 压力过34/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__init_modify__0 | timeout | 1801s | 70轮 随机过40/40 压力过30/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P23__init_modify__1 | timeout | 1802s | 74轮 随机过40/40 压力过34/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane5 |
| L1_P24__relop_replace__7 | timeout | 1801s | 70轮 随机过40/40 压力过30/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P24__const_perturb__9 | timeout | 1802s | 70轮 随机过40/40 压力过30/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P24__const_perturb__4 | timeout | 1801s | 72轮 随机过40/40 压力过32/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P24__const_perturb__13 | timeout | 1802s | 72轮 随机过40/40 压力过32/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |
| L1_P24__index_replace__12 | timeout | 1802s | 72轮 随机过40/40 压力过32/63 整探针超时 | 预算不足(1800s 截断) | 不达标 | 待跑 lane4 |

注:L1_P20__relop_replace__3 在两档各有一条记录;其闭环不是重跑,而是对 envfix 档那次 103 轮记录的离线重判入账(见 2.2),lane4 观测中的记录与 envfix 归档 wall/证据逐项一致(wall 3594s、98 有效轮、随机 35、压力 63)。

### 2.2 envfix 归档(8 条,三道并发资源耗尽)

| probe_id | class | wall | 轮级证据摘要 | 归因 | 重判试算 | 现状 |
|---|---|---|---|---|---|---|
| L1_P96__arith_replace__12 | out_of_memory | 1876s | 49轮 随机过0/40 压力过0/63 作废49(环境) | 显存配额(0.45 轮内 OOM 作废) | 不达标 | 待跑 lane3 |
| L1_P96__arith_replace__14 | out_of_memory | 1879s | 51轮 随机过10/40 压力过11/63 作废30(环境) | 显存配额(0.45 轮内 OOM 作废) | 不达标 | 待跑 lane3 |
| L1_P96__relop_replace__8 | out_of_memory | 2518s | 60轮 随机过0/40 压力过0/63 作废60(环境) | 显存配额(0.45 轮内 OOM 作废) | 不达标 | 待跑 lane3 |
| L1_P20__relop_replace__3 | out_of_memory | 3594s | 103轮 随机过35/40 压力过63/63 作废5(环境) | 显存配额(5 轮 OOM 作废,余轮达标) | STILL(达标) | 重判入账(resource_degraded)→STILL_LIKELY_EQUIVALENT |
| L1_P20__relop_replace__7 | other_unknown | 1110s | 44轮 随机过40/40 压力过4/63 | 主机内存(cgroup SIGKILL 提前终止) | 不达标 | 待跑 lane4 |
| L1_P20__relop_replace__4 | other_unknown | 1357s | 49轮 随机过40/40 压力过9/63 | 主机内存(cgroup SIGKILL 提前终止) | 不达标 | 待跑 lane4 |
| L1_P22__relop_replace__6 | timeout | 3604s | 102轮 随机过1/40 压力过62/63 作废39(环境) 整探针超时 | 争用作废(三道并发显存耗尽)+超预算 | 不达标 | 待跑 lane5 |
| L1_P22__relop_replace__8 | out_of_memory | 2348s | 71轮 随机过0/40 压力过29/63 作废42(环境) | 争用作废(三道并发显存耗尽)+超预算 | 不达标 | 待跑 lane5 |

双档重叠探针(计 1 次):L1_P20__relop_replace__3, L1_P20__relop_replace__4, L1_P20__relop_replace__7, L1_P22__relop_replace__6, L1_P22__relop_replace__8

## 3. 重排队完整性对账(14:35 快照)

| 项 | 值 |
|---|---|
| lane0 拆分目标(全局) | 206 |
| 已完成(completed 并集∩目标) | 7 |
| 待跑 | 199(lane3=98, lane4=47, lane5=54) |
| 完成+待跑 | 206 = 206 ✓ |
| 待跑未被 lanes3/4/5 覆盖 | 0 ✓ |
| 活动观测跨道重复 probe_id | 0 ✓ |
| completed 文件 | lane0=3, lane1=123, lane2=124, lane3=1, lane4=2, lane5=1 |
| 归档探针在队列 | 36 条超时档:4 已闭环 + 32 在队;8 条 envfix:1 已闭环 + 7 在队;无遗漏,无需补队 |

lanes 1/2 已收官(obs 123+124,DONE 标记在),全局 CSE 目标 453 条 LIKELY_EQUIVALENT = lane0 拆分 206 + lanes1/2 247。

## 4. 对症配置矩阵(仍需重跑的 35 条唯一探针)

| 归因类 | 待跑数 | 所在 lane | 对症配置 | 覆盖判断 | 兜底预案 |
|---|---|---|---|---|---|
| 预算不足(1800s 截断) | 28(纯超时类) | 3/4/5 | 3600s 预算 + budget_exhausted 部分证据判级 | 已覆盖:历史 1800s 完成 56–74 轮,3600s 外推 112–148 轮 ≥ 103 计划轮;判 STILL 只需 40+42 过。先例:L1_P16/P20 重跑 2834/3513s 全轮完成 | 若个别再超时,由部分证据判级兜底 |
| 显存配额(P96 族) | 3 | lane3 队首(串行 0.92≈75.3GB) | 串行独占显存 + 3600s | 基本覆盖但余量最小:P96 equiv 中位 953s×3.22≈3069s,且历史 0.45 下全轮 OOM(6GiB 分配失败),0.92 下应可分配 | **专门补跑安排**:若 lane3 跑 P96 再 INC(超时/OOM),CSE 收官后独占窗口重跑:无并发、0.92、`--timeout 5400`、`--lane 3 --lane-tag p96_5400`(需先从 lane3 obs 归档该 INC 记录并从 cse_completed_lane3.json 摘除 id,lane3 停机后操作) |
| 主机内存(cgroup SIGKILL) | 2(P20_relop_4/7) | lane4 | 两道并发上限(host RAM 83/120GB)+ 守护 v10.1 串接 lane5 | 已覆盖:SIGKILL 源于三道并发时代主机内存耗尽;现两道并发 + lane5 串接 | 守护 AUTORESTART + INCCOUNTS 告警 |
| 争用作废(P22 族显存) | 2(P22_relop_6/8) | lane5(0.45,lane4 完成后串接) | 0.45 两道并发 + resource_degraded 判级 | 大概率覆盖:先例 L1_P22__arith_replace__20 在 0.45 下 102/103 轮、随机 40/40 全过判 STILL;历史 OOM 发生在三道并发碎片期 | 若再 INC:转 lane3 尾部(0.92)或并入 P96 独占窗 |
| 合法拒判(equiv) | 0(不重跑) | — | — | 预注册口径保留 INCONCLUSIVE | — |

注:35 条唯一待跑 = 28(纯超时)+ 3(P96)+ 2(主机内存)+ 2(争用作废)= 32(超时档)+ 3(P96 仅在 envfix 档);P20_relop_4/7、P22_relop_6/8 同时在两档(双归因),按更针对性的归因行归类。

## 5. 看护升级(已上线)

- 远端守护升级 v9 → **v10.1**(14:41 部署,pidfile 流程:停 91232/91887 → 改 → 起 91971;两道驱动 PID 89920/90128 全程不变):进度行由 `cse lane L obs=N` 改为 `cse lane L obs=N inconclusive=I`,I = 该 lane 观测文件中 INCONCLUSIVE 计数,每 30 分钟写入 e1_cse_laneL.log。v9 备份于 e1_guard_cse_split_v9.bak.sh。
- 本地看护链路不变:_watch_cse_cycle.py 每 10 分钟独立统计各 lane INCONCLUSIVE 输出 INCCOUNTS 行,_watch_cse.py 对增量报 ALERT_INCONCLUSIVE_GROWTH。远端进度行与本地 INCCOUNTS 构成双通道。
- 当前基线:lane3=0,lane4=0,lane5=0(任何 >0 即告警并触发第二轮清算)。

## 5.1 运行期新增 INCONCLUSIVE(第二轮清算,2026-07-28 凌晨)

| probe_id | lane | class | 证据 | 归因 | 处置 |
|---|---|---|---|---|---|
| L1_P96__launch_config_mutate__0 | 3 | timeout | 3602s 超时,79 有效轮(随机 40/40 过,定向差 3 轮未达 42) | P96 族单轮成本高,3600s 近失(同族其余 10 条均达标判级) | 已在预案内:并入 CSE 收官后 P96 独占窗口(5400s、无并发、0.92) |
| L1_P53__arith_replace__17 | 3 | timeout(实为轮级挂起) | wall 2195s **未**超总预算;第 59 轮 `mixed_extremes` 触发 90s 轮级看门狗后 worker 卡死提前退出;已完成 58 轮(随机 40/40 全过,定向 18/42) | 见下【定性结论】:**原内核同挂**,`mixed_extremes` 对 P53 超大输入的**输入生成**超预算,与变异无关,合法拒判 | 记录不动(不改账);已上线 per-kernel 策略跳过(P53 跳 mixed_extremes/sparse/sparse_extreme);收官窗口从账本摘除本 id 后带跳过重跑,即可正常定级 |
| L1_P53__relop_replace__4 | 3 | other_unknown(实为轮级挂起) | wall 1954s **未**超总预算;同签名:第 59 轮 `mixed_extremes` 触发 90s 轮级看门狗后 worker 卡死提前退出;已完成 58 轮(随机 40/40 全过,定向 18/42) | 同上:原内核同挂,`mixed_extremes` 输入生成超预算,合法拒判 | 同上(记录不动;跳过机制已上线;收官摘 id 重跑) |
| L1_P53__const_perturb__0 | 3 | timeout(实为轮级挂起) | wall 2671s **未**超总预算;同签名:随机 40/40 全过,定向 18 过后 `mixed_extremes` 连续 3 轮 90s 看门狗超时(round_timeout)随后 worker 卡死 | 同上:原内核同挂,`mixed_extremes` 输入生成超预算,合法拒判 | 同上(记录不动;跳过机制已上线;收官摘 id 重跑) |

### 5.1.1 挂起主体定性结论(2026-07-28,原内核对照 + 缩比基准)

**判定:合法拒判(策略输入超出资源契约域),与变异无关。** 三条 P53 INCONCLUSIVE 同签名,均非变异体非终止,而是 `mixed_extremes` 策略对 P53 超大输入的**输入生成**本身超出轮级看门狗/cgroup 内存预算。证据链:

1. **原内核对照(0.18 显存配额、300s/150s 硬超时,不干扰在跑 lane3/lane4)**:对**未变异 P53 原内核**跑同款 `mixed_extremes`(worker 同 seed 50040+si):
   - si=0:输入生成阶段挂起 >150s(连 "input ready" 都未打印);
   - si=1:输入生成阶段被 cgroup OOM 于 92s SIGKILL(-9);
   - si=2:输入生成耗时约 120s 后完成,GPU forward 仅 0.003s。
   → **原内核与变异体表现完全一致**;GPU 前向永远秒回,挂点在 CPU 输入生成,与内核语义/变异无关。
2. **根因(读 `src/stress/policy_bank.py`)**:P53 输入 `torch.rand(128,4096,4095)` = 21.5 亿 float32 元素(单张量 8.6GB)。`_mixed_extremes` 对整张量做布尔掩码 fancy-index 散射两次(`values[mask]*=1e4` / `values[~mask]*=1e-4`,各约 10 亿元素),峰值 CPU 内存 30–40GB,在 120GB cgroup + 并发双 lane 下逼近 OOM 且远超 90s 轮级预算。`sparse`/`sparse_extreme` 同类(布尔掩码散射 + `mask.sum()` 遍历 21 亿 bool)。
3. **缩比基准(1/16 尺寸、峰值 ~0.5GB,安全)外推全尺寸生成耗时**:`sparse`≈115s、`mixed_extremes`≈64s(实测已 >120s/OOM,外推为下界)、`sparse_extreme`≈23s;其余 18 个策略均为廉价向量化(<40s,且生产中 P53 已实测通过前 6 个)。仅这 3 个做全张量布尔掩码散射。

**已实施处置(自动继续跑,未停机):**

- **代码**:`scripts/run_e1_cse_falsify.py` 新增 per-kernel 策略跳过(`load_policy_skip` 自动发现 `<out>/cse_policy_skip.json`;逐探针 `stress_policies` 剔除被跳策略;`grade_cse_evidence` 接收缩减后的 `stress_rounds_planned`)。**判级语义未放松**:stress 通过阈值仍为绝对值 `CSE_MIN_STRESS_ROUNDS=42`,计划轮 63→54,要求通过率由 42/63=66.7% 升至 42/54=77.8%(更严);跳过轮既不计过也不计败(不入 `trials`),不污染 resource_degraded 兜底。远端 CPU `pytest` 51 项全过(新增 `tests/test_cse_policy_skip.py` 6 项 + 既有 CSE/超时判级用例无回归)。
- **配置**:`/root/mk_v2_runs/e1/cse_policy_skip.json`:`{"L1_P53": ["mixed_extremes","sparse","sparse_extreme"]}`,含完整根因/证据留痕。
- **驱动重启(安全,账本完整)**:备份旧驱动 → 上传新代码/配置/测试 → py_compile + pytest 通过 → kill lane3 驱动(PID 89920)及其 worker(看护 91971、lane4 驱动 90128 全程不变);看护 v10.1 于 05:54:19 AUTORESTART 带新代码/配置拉起(新驱动 PID 127575,日志打印 "per-kernel policy skip active for ['L1_P53']",manifest 记 `policy_skip`)。被 kill 的 `const_perturb__4` 无账本条目(账本仅在探针完成时原子写入),遂带跳过逻辑干净重跑(新 cfg 仅 18 策略、已排除 3 个,已核对),避免再产 1 条废 INCONCLUSIVE。3 条已记录 INCONCLUSIVE 的账本条目**未改动**。

基线更新:lane3 现存运行期 INCONCLUSIVE = P96__launch_config_mutate__0(预算类,预案内)+ 3 条 P53(mixed_extremes 合法拒判,跳过机制已上线);均不进终版统计。lane3/4/5 剩余 P53:仅 **lane3 有 P53**(lane4/lane5 计划中 P53=0);活动队列剩余 7 条 P53(const_perturb__4 重跑中、__7、index_replace__8/__12、mask_boundary__0/__3/__5)将带跳过逻辑正常跑;另 3 条已记录 INCONCLUSIVE 的 P53 待收官窗口摘 id 重跑。哨兵 R1 阈值(4h 内 ≥3)—— 3 条 P53 均系同一 mixed_extremes 系统性成因、已对症闭环,不作为独立新增异常升级。

### 5.1.2 运行期新增第 5 条(2026-07-28 20:57,lane3)

| probe_id | lane | class | 证据 | 归因 | 处置 |
|---|---|---|---|---|---|
| L1_P52__arith_replace__11 | 3 | other_unknown | wall 1457s 未超预算、未触发超时;59 轮全 pass(随机 40 + 定向 19)后记录戛然而止,无发散、无 stderr;evidence 带 partial_result=true(59/103) | worker 在第 60 轮附近被静默 SIGKILL(驱动抢救了部分快照):第 60 轮正处 mixed_extremes 相邻轮次,P52 为大输入内核(同内核 worker RSS 实测 49GB),疑似瞬时 cgroup OOM 击杀(cgroup oom_kill 计数含既往取证击杀);**签名与 L1_P53__relop_replace__4 完全一致,属同一失败模式家族**(大输入 × mixed_extremes 内存尖峰 × 瞬时 OOM) | 一次性事件:同内核后续 3 条探针(102/101/103 轮)全部正常完成,无复发;纳入收官独占窗重跑(独占窗无并发,内存余量翻倍,预期一次通过)。**升级预案**:若 P52 再出同签名 INC(当前 1/12,低于 P53 当时 3 条的处置阈值),将 mixed_extremes 加入 P52 的 per-kernel skip(机制与先例现成) |

基线更新:运行期 INCONCLUSIVE 共 **5 条**(1×P96 预算类 + 3×P53 合法拒判 + 1×P52 瞬时 OOM),全部已归因、有重跑路径,均不进终版统计;收官独占窗重跑清单相应为 5 条。(已被 5.1.3 更新为 7 条。)

### 5.1.3 同签名蔓延:第 6、7 条与根因查实(2026-07-29 上午,第三轮清算)

| probe_id | lane | class | 证据 | 归因 | 处置 |
|---|---|---|---|---|---|
| L1_P46__relop_replace__5 | 3 | other_unknown | wall 1416s 未超预算未超时;58 轮全 pass(随机 40 + 定向 18)后戛然而止,无 stderr,partial_result 快照;死于第 59 轮 = **mixed_extremes si=0 执行中**(P52 同签名) | 瞬时 cgroup OOM 静默 SIGKILL(见下【根因查实】):lane3×lane5 双大内核并发,本 worker mixed_extremes 生成尖峰击穿 120GiB | 记录不动;并入收官独占窗重跑清单;根因已由 cse_mem_fix_v1 对症闭环(见 5.3) |
| L1_P23__mask_boundary__1 | 5 | other_unknown | wall 1008s 未超预算未超时;56 轮全 pass(随机 40 + 定向 16)后戛然而止,无 stderr;死于第 57 轮 = all_positive si=1(**非**高内存策略) | 同一次内存危机的**连坐击杀**:与 P46 死亡时刻仅差 7 秒(02:04:16 vs 02:04:23 UTC),lane3 的 P46 worker 在 mixed_extremes 尖峰时,本 worker 高基线(HWM 实测 30.6GB 量级)被 OOM killer 一并选中 | 同上 |

**蔓延时间线(北京时间):**

- 07-28 12:56 cse_gen_opt_v1 部署(lane3/lane4 重启);此后与 lane4 并发的 ~7h **零事件**(lane4 均为中小内核,12:57-20:05 正常收官)。
- 07-28 20:06:56 守护链式拉起 lane5(P22/P23 族,单份输入 6.4GB,全部大内核)。
- 07-28 20:57:37 **P52__arith_replace__11**(lane3,8.6GB 内核,mixed_extremes si=1 执行中)——lane5 上线后仅 51 分钟,当时 lane5 正处 P22__relop_replace__8 压力段。
- 07-29 10:04:16 / 10:04:23 **P23__mask_boundary__1(lane5)与 P46__relop_replace__5(lane3)7 秒内双杀**:P46 正进 mixed_extremes,P23 被连坐。
- 三条事件全部落在 lane3×lane5 大内核并发期;lane3 恰好走到自己的大输入段(P49→P52→…→P46,均 128×4096×4095=8.6GB/份)。

**根因查实结论:推翻"模板缓存抬高基线"假设,确认"双 lane 大内核并发 × 高内存策略瞬时尖峰"。**

1. **缓存排除(代码级)**:对照 v1 diff,旧代码每压力轮的局部变量 `template` 同样在整个压力阶段常驻一份完整输入树(直到下轮重新赋值才释放),v1 的单模板缓存 live-set 与之相同;且 v1 还移除了外层 clone_tree(峰值反而少一份 8.6GB)。缓存没有抬高基线,也没有抬高峰值。
2. **缓存排除(经验级)**:v1 部署后与 lane4 并发的 7 小时零事件(含历史双杀户 P20__relop_replace__4 全 103 轮通过、双 worker RSS 峰 99GB);三条事件与部署时刻不重合,与 **lane5 上线(20:06)** 强相关(首条仅隔 51 分钟)。
3. **OOM 实证**:cgroup v1 `memory.oom_control` oom_kill=16(含既往取证击杀),`memory.max_usage_in_bytes`=128849141760 **顶格 120GiB 限额**;dmesg/journalctl 容器内不可见;哨兵心跳(10 分钟采样)在 01:58/02:08 仅 21.9/29.1GB → 尖峰为瞬时(秒级),采样抓不到,与"戛然而止无 stderr"的静默 SIGKILL 签名一致。
4. **内存账**(fp32;P22/P23=6.4GB/份,P46/P49/P52/P53=8.6GB/份):worker 在压力轮驻留 ≈3 份全尺寸(缓存模板 + 上一压力轮 stress_inputs/input_values 残留 + 随机轮 generated 残留,后两份为**新旧代码共有**的陈旧引用),mixed_extremes 生成期再叠 ≈3-4 份瞬时(clone + randn + rand→bool 掩码 + 花式索引散射)→ P46 worker 峰值 ≈55-60GB;对面 P23 worker 即便在廉价策略轮也驻留 ≈4-6 份 ≈45-50GB;加两份 torch/CUDA 宿主开销(~5-6GB/worker)≈ 110-120GB,击穿 120GiB。与 P52 内核 worker RSS 实测 49GB、P23 worker HWM 实测 30.6GB(随机轮阶段)相容。

基线更新:运行期 INCONCLUSIVE 共 **7 条**(1×P96 预算类 + 3×P53 合法拒判 + 3×大内核并发瞬时 OOM:P52/P46/P23),全部已归因、有重跑路径,均不进终版统计;**收官独占窗重跑清单 = 7 条**(P96__launch_config_mutate__0、P53__arith_replace__17、P53__relop_replace__4、P53__const_perturb__0、P52__arith_replace__11、P46__relop_replace__5、P23__mask_boundary__1)。独占窗无并发、内存余量翻倍,且已带 cse_mem_fix_v1,预期一次通过。

## 5.2 输入管线 bit-exact 优化部署留痕(2026-07-28 12:56,导师批准)

**变更**:CSE worker 输入生成管线优化(`cse_gen_opt_v1`):stress 轮单模板缓存(仅全浮点张量树,守卫回退)+ 去冗余外层 clone_tree + summaries 单遍 aminmax。**输入张量与 summaries 逐 bit 等价**(部署门禁:341 项张量 torch.equal + 336 项 summaries 逐 bit 对照全绿,覆盖 P1 全尺寸 / P53、P96 缩比全 21 策略×3 seed / P53 全尺寸 8.6GB / 混合树守卫路径);**判级语义零改动**(grade_cse_evidence、42/63 阈值、policy skip 均未触碰)。详见《E1_CSE_单探针耗时剖析与加速评估.md》第三部分。

- **代码**:`scripts/_mutant_worker.py`(~55 行)、`scripts/run_e1_cse_falsify.py`(8 行,manifest+记录加 `input_pipeline` 标记);policy_bank 零改动。新增 `tests/test_gen_opt_bitexact.py` 21 项;远端 CPU pytest **257 全过**无回归。备份 `*.bak_20260728_preopt`。
- **驱动重启(安全,账本完整)**:kill 前后 obs 行数(lane3=25/lane4=31)与 completed md5 逐字节一致;**先杀驱动(90127/90128/127575)后杀 worker**(避免旧驱动把半截结果写成 INCONCLUSIVE);守护 v10.1 于 12:56:37 AUTORESTART 拉起新驱动 lane3=146300 / lane4=146306;被杀 in-flight 探针(P35__arith_replace__16、P20__relop_replace__4)无账本条目,干净重跑。
- **部署后首两条探针**:P35__arith_replace__16 → **FALSIFIED**(witness structured_ramp/sub0/seed50040,证据链完整);P20__relop_replace__4(历史两次 cgroup SIGKILL 户)→ STILL_LIKELY_EQUIVALENT,**103/103 全轮完成**,wall 1865s(同族旧中位 3300-3600s,−45%)。无新增 INCONCLUSIVE,无 OOM(双 worker RSS 峰 99GB < 120GiB)。
- **口径**:**2026-07-28 12:56:37 为 wall_ms 断点**,此后记录带 `input_pipeline: "cse_gen_opt_v1"`,墙钟不可与之前直接比较;判级不受影响、跨断点可比。§4 对症配置矩阵中"3600s 预算"的覆盖判断只会更宽松(单探针成本 −45% 以上),P96 独占窗口(5400s)预计不再必要,届时按实际情况裁定。
- **收官预计更新**:lane3 剩 73 条 ≈ 36-40h;lane4 剩 17 条 ≈ 9h;lane5(54 条,串接自动继承新代码)≈ 28.5h;关键路径 ≈ **1.6 天**(原 ~3 天)。

## 5.3 并发主机 OOM 加固部署留痕(cse_mem_fix,2026-07-29 上午,最终形态 v1.2)

**动机**:5.1.3 查实的"双 lane 大内核并发 × 高内存策略瞬时尖峰"击穿 120GiB cgroup。最终部署三项措施,全部语义中性(只是更早释放引用、或改变执行时序),输入与 summaries 保持逐 bit 等价,判级语义零改动:

1. **陈旧引用即时释放**:随机轮与压力轮在 `_evaluate` 返回后立即置空 `generated`/`stress_inputs`/`input_values`/`args`(轮级超时路径同),砍掉新旧代码共有的 ~2 份全尺寸跨轮驻留 → 实测 worker 轮间 RSS 从 ~30-50GB 回落到 **3-5GB**(压力段间隙)。
2. **高内存策略轮前防御性清扫**:`mixed_extremes`/`sparse`/`sparse_extreme`(`HIGH_MEM_STRESS_POLICIES`)生成前 `gc.collect()` + `torch.cuda.empty_cache()`(在 `_seed_all` 之前,不触碰任何 RNG 流)。
3. **跨 worker 高内存生成串行化(v1.1)**:模板树 >1GiB(`HIGH_MEM_GATE_MIN_TEMPLATE_BYTES`,`_needs_highmem_gate`)的 worker 在高内存策略轮的输入生成段持 `flock`(`/tmp/mk_cse_highmem_gen.lock`),两 lane 的生成尖峰**永不同时**;锁在 90s 轮级看门狗 alarm 之前获取(等锁不烧轮预算),policy 返回即释放,持锁进程死亡自动释放,纯时序不改任何数值。小内核(≤1GiB)不进闸,无额外开销。

**stress 模板缓存保留(v1 行为不变)**。上午迭代留痕:10:27 初版曾对 >1GiB 模板禁用缓存(逐轮重生成),两条实测(见下)显示大内核墙钟 +30-45%、P46 族逼近 3600s 预算;且按实测账,最坏对撞是"尖峰∩尖峰"——此时两侧各有一份模板活跃,禁不禁缓存驻留相同,禁用只降均值不降尾部 → 11:36 收敛为 v1.2(恢复缓存 + 依赖措施 1-3),经 staged 门禁热替换(worker 每探针一进程、派生时读盘,无需杀进程)。

**内存账(实测校准)**:8.6GB 内核 mixed_extremes 生成尖峰 HWM 实测 **72GB**(6.4GB 内核折算 ≈55GB);措施 3 保证高内存尖峰独占;对面 worker 最坏为廉价策略克隆尖峰 ≈3.5 份+开销 ≈35GB(8.6GB 内核)→ 最坏对撞 ≈**107GB < 120GiB**;评估期/轮间对面仅 ≈12-22GB,典型并发 ≈85-95GB。

- **代码**:`scripts/_mutant_worker.py`(`INPUT_PIPELINE_TAG` → **cse_gen_opt_v2**;新增 `HIGH_MEM_STRESS_POLICIES`/`HIGH_MEM_GATE_MIN_TEMPLATE_BYTES` 常量、`_tree_tensor_nbytes`/`_needs_highmem_gate`/`_acquire_highmem_lock`/`_release_highmem_lock`、压力轮释放与闸门逻辑;另修一处 v1 隐患:非全浮点树首个模板不再被缓存引用常驻);`scripts/run_e1_cse_falsify.py` 仅 manifest `input_pipeline` 描述文本。policy_bank 与判级(`grade_cse_evidence`/42 阈值/policy skip)零改动。备份 `*.bak_20260729_pre_mem_fix`。
- **测试**:新增 `tests/test_cse_memfix.py` 10 项(`_tree_tensor_nbytes`、闸门阈值与事发内核尺寸、缓存/重生成路径 stress 输入逐 bit 相等、flock 互斥与释放、gc 清扫不扰动 RNG 流);每版先 staged 门禁(`MK_WORKER_PATH` 指向暂存 worker,21+10 项)再安装;安装后远端 CPU `python -m pytest tests -q` **267 全过**(原 257 + 新增 10,无回归)。
- **部署流程(账本完整)**:10:27 初版走停-改-起先例——kill 前后 obs 行数(lane3=57/lane5=35)与 completed md5 逐字节一致,先杀驱动(146300/164619)后杀 worker,守护 v10.1 于 **10:27:33 AUTORESTART** 拉起 lane3=200586 / lane5=200592,manifest 带 cse_gen_opt_v2、policy skip(L1_P53)正常加载,被杀 in-flight 探针(P46__relop_replace__0、P23__init_modify__0)无账本条目干净重跑;v1.1(11:15)/v1.2(11:23)为 worker 文件原子热替换,驱动与在跑 worker 不动,下一探针派生自动生效。注:两驱动 manifest 的 `input_pipeline` 描述文案停留在 10:27 初版措辞,逐条记录的 `input_pipeline` 标记(worker 写入)为准,下次驱动自然重启时 manifest 自动刷新。
- **部署后实测**:lane5 `L1_P23__init_modify__0` → STILL_LIKELY_EQUIVALENT,103 轮,wall 2722s(初版禁缓存代价可见);lane3 `L1_P46__relop_replace__0` → STILL_LIKELY_EQUIVALENT,wall 3554s(距预算 46s,触发 v1.2 收敛);oom_kill 计数保持 16 无增量,双 worker 并发 cgroup 用量 4-21GiB(此前同工况 30-50GB 常驻)。
- **口径**:v2 与 v1 判级完全可比;v1.2 下大内核 wall_ms 恢复至 v1 水平(仅高内存轮偶发等锁,期望每锁 ~3s)。
- **v1.2 实测(12:29 快照)**:lane3 `L1_P46__const_perturb__0`(首个 v1.2 worker)→ STILL,wall **2501s**(初版 v2 同族 3554s,v1 同族 2400-2700s,速度已恢复);lane5 `L1_P90__arith_replace__6` → STILL,1221s;两 lane 运行期 INCONCLUSIVE 计数无增长(lane3=6、lane5=1,与 5.1.3 账目一致),oom_kill 计数保持 16。
- **收官预计(2026-07-29 12:30 更新)**:lane5 余 17 条(P90/P98/P25/P5,中小内核,~1000-1300s/条)≈ **今晚 18-19 点收官**;lane3 余 40 条(P46 余量 + P94/P93/P37/P51/P47/P48/P19/P16/P21/P39,大小混合,均值 ~2000-2200s)≈ 22-24h → **7-30 中午前后收官**;随后独占窗:P96 专窗(5400s)+ 7 条重跑清单(见 5.1.3)+ equiv P95 重试 ≈ 6-7h → **7-30 傍晚全部清算完毕**。

**v1.1 追加(2026-07-29 11:05,热替换,零停机)**:部署后压力段实测,P46 worker 轮间 RSS 已回落至 4-5GB(修复前 ~30-50GB 常驻,措施 1/2 起效),但 mixed_extremes 生成瞬时 HWM 实测 **72GB**(8.6GB 模板;6.4GB 模板折算 ≈55GB)——若两 lane 高内存轮恰好同瞬叠加(72+55≈127GB)仍可能擦破 120GiB。遂追加第 4 项纯时序措施:**大模板(非缓存类)高内存策略的输入生成段跨 worker `flock` 串行化**(`/tmp/mk_cse_highmem_gen.lock`;加锁在 90s 轮级看门狗启动之前,等待不占轮预算;policy 返回后立即放锁;进程死亡自动释放,无死锁;纯排队不改任何生成值,bit-exact 天然成立)。串行化后最坏并发 = 一侧尖峰 72GB + 另侧轮间驻留 ≈15GB ≈ 87GB,余量 ≥33GB。部署方式:worker 文件原子 mv 热替换(worker 每探针一进程、派生时读盘),驱动与在跑 worker 全程未动,账本零风险;staged 门禁 31 项 + 远端 `pytest tests -q` **267 全过**(新增 2 项 flock 排他/释放测试)。

## 6. 收官独占窗自动衔接(2026-07-30 00:38 部署上线)

lane3 收官 → 独占窗清算全自动衔接,零空转、无需人工值守。**红线:#7 复核与 P95 重试只产出证据文件和建议,不自动改主账;定级决定留给人工确认。**

### 6.1 触发链路

```
lane3 驱动打印 "cse-falsify DONE"
  → 守护 v10.1 下一巡检周期(≤120s)touch /root/mk_v2_runs/e1/CSE_DONE_LANE3
  → 三 lane 标记齐 → 守护写 CSE_DONE 并自行退出(已读脚本确认:守护自然退出,
    且其 AUTORESTART 以标记文件为先决阻断、pgrep 匹配 "--lane N$" 结尾,
    不会误拉起/误杀带 --lane-tag 的清算驱动)
  → 触发器 _final_window_trigger.sh(远端 PID 232294)每 60s 检测
    [ -f /root/mk_v2_runs/e1/CSE_DONE_LANE3 ](直接测标记文件;吸取上次
    _cse_split_trigger.sh grep 日志找空文件标记失败的教训)
  → 启动编排脚本 /root/mk_v2/_final_window_go.py(单例锁 + 幂等,失败 600s 重试)
```

- 监听路径核对:守护第 38 行 `MARK=$RUNS/e1/CSE_DONE_LANE$L` 展开值与触发器默认 `FW_MARK` 逐字符一致(`MARKER_PATH_MATCH`),并与实际已存在的 `CSE_DONE_LANE4`/`LANE5` 空文件同目录同命名。
- 哨兵 e1_sentinel.py(PID 108721)继续在岗:其账本读取按精确文件名(`cse_observations_lane{3,4,5}.jsonl`)、进程识别按 `--lane N` 结尾,均不触碰清算驱动与 tagged 文件;lane 标记齐后其主动规则对空活动 lane 集自然空转。

### 6.2 编排步骤(串行,单驱动独占全卡,MK_GPU_MEMORY_FRACTION=0.92)

日志:`/root/mk_v2_runs/final_window.log`;全部完成写 `/root/mk_v2_runs/e1/FINAL_WINDOW_DONE` + `final_window_summary.json`。

| 步骤 | 内容 | 配置 |
|---|---|---|
| 0 | 前置:确认 lane3 驱动进程退出(pgrep 轮询,上限 30min)、守护自然退出(上限 15min,超时仅 WARN——标记已阻断其重启逻辑,安全) | 不动哨兵 |
| 2a | 摘账 P96__launch_config_mutate__0 → 重跑 | `--lane 3 --lane-tag p96_5400 --timeout 5400` |
| 2b | 摘账 P53__arith_replace__17 / relop_replace__4 / const_perturb__0(cse_policy_skip.json 对 P53 自动生效,跳 3 策略)+ P52__arith_replace__11 + P46__relop_replace__5 → 重跑 | `--lane 3 --lane-tag final_requeue --timeout 3600` |
| 2c | 摘账 P23__mask_boundary__1(lane5)→ 重跑 | `--lane 5 --lane-tag final_requeue --timeout 3600` |
| 3 | #7 翻案定向复核(证据 only) | 见 6.3 |
| 3b | P37 全灭集群自稳定性对照 + 复现(证据 only,2026-07-30 10:01 点火前增补) | 见 6.3b |
| 4 | P95__relop_replace__5 equiv 崩溃重试(证据 only) | 见 6.4 |

摘账机制(分段进行,每段只在对应重跑前执行,保证 P96 独享 5400s 预算):原 INCONCLUSIVE 记录**原文移入** `cse_observations_inc_archive_v2.jsonl`(不删),对应 id 从 `cse_completed_lane{3,5}.json` 摘除;编辑前四个账本文件各留 `*.bak_final_window` 备份;原子写、逐 id 幂等(重入安全)。重跑观测写独立 tagged 文件 `cse_observations_lane3_p96_5400.jsonl` / `cse_observations_lane{3,5}_final_requeue.jsonl`——命名保持 `cse_observations_lane*` glob 形状,最终清算合并时自动并回;驱动 skip 集读全部 `cse_completed_lane*.json`,不会重复跑已完成探针。判级语义零改动(仍是现行预注册 `grade_cse_evidence`)。

### 6.3 #7 复核协议与判据(L1_P46__index_replace__5)

witness = mixed_extremes / sub 1 / seed 50041,原 candidate_crash 实为 90s 轮级看门狗超时。复核:轮级看门狗放宽至 **300s**,candidate 同 seed 重跑 3 次 + 未变异对照(原内核作 candidate)1 次;seed 精确复现已核实——worker 压力轮 seed = base_seed + equiv_runs + si(与策略列表无关),取 `equiv_runs=0, base_seed=50040` 得 50040/50041/50042。判据:

- candidate 3/3 稳定超时/发散 且 对照正常完成 → **建议维持 FALSIFIED**,witness 升级为可复现记录;
- candidate 3/3 在 300s 内正常完成且输出一致 → **建议该轮环境作废**,探针按剩余证据重新判级;
- 混合 → 人工逐份复核。

产出:`/root/mk_v2_runs/e1/final_window_review/p46_index_replace_5/`(逐次 result JSON + review_summary.json + RECOMMENDATION.txt)。**不写主账。**

### 6.3b P37 全灭集群复核协议与判据(第九轮探查增补,H1/H2 判别)

背景:P37 全部 5 条 LIKELY_EQUIVALENT 探针(F-ARITH / F-SYNC×2 / F-LAUNCH / F-EPS)在完全相同轮位(第 74 轮 = **boundary_last_element / sub 0 / seed 50040**,输入 112×64×512×512、末元素置 10000.0)翻案 FALSIFIED,oracle 全部"恰 1 个值超差",max_abs_error 0.035–0.182(容差 0.01),此前 73 轮全过。**H1** = 边界盲区幸存者被边界定向策略团灭(独立真缺陷);**H2** = 原内核对末元素极值的归约顺序敏感,任何调度扰动都让该单值漂移(同一交互的重复观测)。

复核协议(机制平移 6.3,`equiv_runs=0, base_seed=50040, stress_policies=["boundary_last_element"], stress_repeats=1` 精确复现 witness seed;round_timeout 维持生产值 90s——原翻案是数值超差非超时):

1. **原内核自稳定性对照 ×3**:未变异 P37 原内核作 candidate vs 参考路径,同款输入,3 遍独立 worker 进程(独立 CUDA 上下文);
2. **翻案复现 ×2×3**:抽检误差两端 `L1_P37__sync_remove__0`(0.182,最大)与 `L1_P37__epsilon_modify__0`(0.035,最小),各同 seed 独立复跑 3 遍,记录超差是否稳定复现、max_abs_error 是否稳定。

判据:

- 对照任一遍超差 → **支持 H2**:原内核自身 vs 参考在该输入即超差,5 条翻案疑为同一"内核×末元素极值×归约顺序"交互,建议 witness 作废/降权并按剩余证据重新判级或换稳健 oracle 复核;
- 对照 3/3 通过 且 两条抽检 3/3 稳定复现超差 → **支持 H1**:维持 5 条 FALSIFIED,witness 升级可复现;
- 对照通过但翻案未复现 → 原 witness 疑瞬态,人工决定是否 5 条全量复现;
- 混合 → 人工逐份复核。

产出:`final_window_review/p37_cluster/`(control_rep1-3 / 各候选 rep1-3 的 result JSON + review_summary.json + RECOMMENDATION.txt)。**不写主账,H1/H2 定夺留给人工。**

### 6.4 P95 equiv 崩溃重试协议(L1_P95__relop_replace__5)

镜像 equiv 阶段原配置(equiv_runs=20、base_seed=10000、round_timeout=90s)candidate 重跑 1 次 + 未变异对照 1 次:崩溃确定性复现且对照健康 → **建议按严格 Oracle 判 SPEC_VIOLATION**(实锤非等价);瞬态消失 → 按本次判级出建议;对照也异常 → 人工排查环境。产出:`final_window_review/p95_relop_replace_5/`。**不写主账。**

### 6.5 部署自检与演练留痕(2026-07-30 00:32–00:38)

- 语法:编排脚本 `py_compile` 通过、触发器 `bash -n` 通过;
- 端到端演练:独立 drill 环境(假标记 `FW_DRILL_FAKE_MARK` + 独立 log/lock + `--dry-run`)——触发器 60s 内发现假标记 → 编排 dry-run 完整走 5 步(7 条 id 全部命中账本:lane3 6 条 + lane5 1 条;seed 推导、驱动命令行、摘账数目全部与预期一致)→ exit=0 → `FINAL_WINDOW_TRIGGERED_OK` → 触发器自净退出;演练日志留存 `final_window_trigger_drill.log`;
- 账本零改动核对:dry-run 前后 lane5 obs/completed md5 逐字节一致;lane3 变化仅为在跑驱动追加新观测(行数只增),无 FINAL_WINDOW_DONE、无残留锁;
- 假标记已清除,真实触发器 00:37:55 上岗(PID 232294,`watching=/root/mk_v2_runs/e1/CSE_DONE_LANE3`,无 dry-run 参数);lane3 驱动 200586、守护 91971、哨兵 108721 全程未受影响。
- **P37 步骤增补部署(2026-07-30 10:01,点火前)**:原已验证脚本备份 `_final_window_go.py.bak_pre_p37`;新版先在临时路径 `py_compile` 通过后原子 `mv` 替换(规避点火竞态),正式路径二次 `py_compile` 通过;随后全量 `--dry-run` 复验——原 5 步输出与 00:36 演练逐条一致,新 STEP3b 正确落位于 STEP3 与 STEP4 之间(协议、探针 id、seed、输出目录均正确);触发器/lane3 驱动全程未动。

### 6.6 预计时间线

lane3 DONE(预计 7/30 中午前后)→ ≤2min 守护写标记并退出 → ≤60s 触发器点火 → step0 ≤5min → 2a P96(5400s 预算,预计 1–1.5h)→ 2b 5 条(约 3–3.5h)→ 2c 1 条(约 0.75h)→ step3 #7 复核(约 0.5–1h)→ step3b P37 复核(9 遍独立 worker,约 0.5–1.5h)→ step4 P95(约 0.5h)→ **FINAL_WINDOW_DONE,共约 7–9h**(收官当天深夜自动清算完毕,次日上午人工确认 #7、P37 与 P95 的建议)。

---

- 判级语义未改:重判试算只调用远端现行部署的预注册 `grade_cse_evidence`;本轮 0 条新写账。
- 已完成 STILL/FALSIFIED/WITNESSED 记录未动;归档文件原样保留。
- 守护修改走停-改-起,期间 lane3/4 驱动不受影响(PID 快照核对一致)。
- 未 git commit。

---

## 7. 导师签认与执行(2026-07-30 16:15 CST 签认,当日执行)

### 7.1 三项签认决定

| 项 | 决定 | 执行方式 |
|---|---|---|
| #7 `L1_P46__index_replace__5` | 同意 `DOWNGRADE_ROUND_ENV_VOID`:90s 看门狗 candidate_crash 判为环境伪证,撤销 FALSIFIED | witness 轮作废后剩余证据 58 轮(压力轮约 18 < 预注册门槛 42),**不足以直接改判**,故按签认条款"不达标则补跑到出级"摘账重跑 |
| P37 集群 5 条 | 同意 `H2_KERNEL_NUMERIC_SENSITIVITY`:未变异对照自身 2/3 发散且同量级,witness 作废 | `boundary_last_element` 对 L1_P37 记为 **oracle 无判别力**写入 policy-skip(附 H2 证据),5 条摘账重跑;剩余 73 轮同样低于门槛,故同样走重跑而非直接改标 |
| P95 `L1_P95__relop_replace__5` | 同意判 SPEC_VIOLATION:崩溃确定性复现、未变异对照干净 | equiv 账本已直接改判落账(原记录归档 `equiv_observations_signoff_archive_v1.jsonl`),equiv 终版 **LIKELY 453 / WITNESSED 74 / INCONCLUSIVE 0** |

**重要口径澄清**:三项签认**不等于**预先钉死重判结果。#7 与 P37 五条是把判级重新打开后**重新做实验**,终局由预注册 `grade_cse_evidence` 依重跑证据裁决,可能落 STILL 也可能再度 FALSIFIED。任何"签认后 FALSIFIED 必为 8"的推算都只是条件预测,不得先行填表。

### 7.2 资源争用事故与处置(16:34—16:58)

签认补跑首启期间,E3 前置 B9 校准以 4 道并发同时占用主机内存(单单元 RSS 峰值 47—79GB,如 L1_P24 LogSoftmax / L1_P33 BatchNorm),在 120GiB cgroup 上限下与 CSE worker 相撞:

- 证据:`oom_kill` 计数由 16 连涨至 **20**(mem_fix 后本已 53.5 小时零增量);#7 补跑 worker 在 999s、**32/103 轮**处被静默杀死,被记为 INCONCLUSIVE;B9 侧亦有 1 条 `run_error exit=-9`(SIGKILL);
- 处置:16:56—16:58 停止 B9 全部 4 道与 guard(按显式 PID 精确终止;`pkill -f` 会匹配 SSH 会话自身命令行并打断连接,已列为操作红线),置暂停标记 `PAUSED_FOR_SIGNOFF_RERUN`,B9 断点 31/200 单元完整保留;
- 该 #7 INCONCLUSIVE 记录**属资源污染而非判级结论**,不得计入任何统计,须在独占条件下重跑。

### 7.3 自动清算器(`_signoff_orch.py`,17:03 上岗)

远端独立编排进程,职责:等在跑驱动退出 → 检查 6 条探针判级 → 对任何 INCONCLUSIVE **自动摘账归档 + 独占重跑**(预算 5400s、轮看门狗 300s),最多 3 轮;**每轮启动前校验 GPU 独占性**(存在非 CSE 的 GPU 占用者则拒绝启动并记录,宁可停也不产出被污染的记录);全过程记录 `oom_kill` 前后计数以便归因。产出 `signoff_orch_summary.json` 与 `SIGNOFF_ORCH_DONE`。

### 7.4 冻结阶段待办口径(供收官执行,勿提前填表)

1. **P37 重跑记录字段修正**:驱动对 policy-skip 一律写 `policy_skip_reason: resource_domain_violation`,而 P37 的跳过理由是 **oracle 无判别力**,冻结前须改为 `oracle_indiscriminative_for_kernel` 并加 `reclassified: kernel_numeric_sensitivity` 溯源;
2. **P95 计列口径**:计入 Table 10 "Witnessed non-equivalence" 列,但加脚注标明其 witness 类型为崩溃型(SPEC_VIOLATION)而非数值发散型,以免夸大"数值发散"口径;
3. **Table 10 INCONCLUSIVE 列**:正文绑定"盲审等价审计后仍 INCONCLUSIVE(κ)",人工盲审未做前**不填**;执行级 INC(CSE 0 / equiv 0 / baseline 25)只作备查,不等同于该列;
4. **Witnessed 列数值以冻结账本实算为准**:两轮离线核查分别给出 82 与 81 的预测值(且均基于签认前账本),存在分歧,冻结后必须重算而非沿用任一预测;
5. **headline 反例 replay bundle 独立复放**:蓝图 §5.1.3 的承诺,须在填 headline 声明前完成。
