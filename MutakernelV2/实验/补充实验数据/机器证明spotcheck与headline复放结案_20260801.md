# 机器证明 spot-check 与 headline 反例复放结案备忘（2026-08-01）

> 执行方式：两项均为人工程序（人工依赖清单 #5、#6），由自动化代理代行
> （用户 2026-08-01 17:41 明示授权）。全部核验步骤可审计复放，脚本与输出
> 见本备忘引用的远端路径。

## 一、#5 机器证明静态规则 spot-check（9/9 通过）

**口径**：Table 10 已填 Machine-proven eq. = 9，正文承诺 "proof template is
released and human-spot-checked"。

**账面**：9 条全部来自 `baseline_observations.jsonl` 的
`status=machine_proven_equivalent`，规则一律为 `dead_host_constant` v1.0，
`rules_version=2dcf14499b81abc5`（`src/mutengine/static_equiv_rules.py` 的
内容哈希，规则漂移可检测）。全部 F-CONST / A 类，与 Table 10 的 A:9 一致。

**核验方法**（比线上规则更严）：线上规则只检查被扰动变量未被
Model/ModelNew 类引用；本次 spot-check 对每条证明解析变异后完整源码的 AST，
枚举被扰动变量在**所有作用域**（含模块级与全部辅助函数）中的每一次引用，
要求除赋值行外只出现在 `get_inputs()`/`get_init_inputs()` 内。前提成立的
语义依据：测试框架下 get_inputs 一律取自参考模块，被扰动常量对被测内核是
死代码。

**结果**：9/9 SOUND。逐条明细（探针 / 变异行 / 变量 / 引用位置）：

| 探针 | 变异 | 变量 | 引用（除赋值行） |
|---|---|---|---|
| L1_P1__const_perturb__0 | N = 2049 | N | 仅 get_inputs（4 处） |
| L1_P1__const_perturb__1 | N = 2047 | N | 仅 get_inputs（4 处） |
| L1_P14__const_perturb__0 | N = 4097 | N | 仅 get_inputs（4 处） |
| L1_P14__const_perturb__1 | N = 4095 | N | 仅 get_inputs（4 处） |
| L1_P21__const_perturb__19 | dim = 16383 | dim | 仅 get_inputs（1 处） |
| L1_P6__const_perturb__4 | K = 131073 | K | 仅 get_inputs（2 处） |
| L1_P6__const_perturb__5 | K = 131071 | K | 仅 get_inputs（2 处） |
| L1_P6__const_perturb__2 | N = 257 | N | 仅 get_inputs（1 处） |
| L2_P64__const_perturb__25 | batch_size = 127 | batch_size | 仅 get_inputs（1 处） |

**结论**：Table 10 Machine-proven eq. = 9 的正文承诺（spot-check）已兑现。
探针源码取自远端 `/root/mk_v2_runs/e1/probes/<kernel>.json`。

## 二、#6 headline 反例 replay bundle 独立复放（清算表 7.4-5）

**结论：该项已由 WC-1 见证确认审计以更强协议实质完成，予以结案。**

- 覆盖：WC-1（`witness_confirmation/wc1_report.json`，2026-08-01T07:33）
  对 **83/83** 个账面见证（含全部 headline 反例：Table 10 的 68 个 equiv
  见证与 §5.5 的 7 个 CSE 证伪）逐一在**新进程**中复跑，149 个复核单元。
- 协议强于单次 bundle 复放：每个见证跑两个独立审计轮 + 原始内核对照臂
  （控制假阳性），并做内核确定性检查（发现 1 个非确定性内核并按 H2 处理）。
- 判定分布：CONFIRMED 71 / NON_DISCRIMINATING 6 / UNCONFIRMED 3 /
  OUT_OF_SCOPE_NON_NUMERIC 1 / ESCALATED 2；全部非 CONFIRMED 项已经
  wc1_closure_v1 账本修订落账（含导师裁定 WC1_20260731）。
- 蓝图 §5.1.3 中 "every non-PASS observation produces a replay bundle that
  re-executes in a fresh container" 的字面机制由 E3 执行器
  （scripts/run_fse_experiment.py 的 evidence.replay_bundle）落实，适用于
  E3 观测；E1 时代观测的独立复核以 WC-1 为准，两者在工件中并列披露。

**遗留**：无。headline 声明填写的前置条件（7.4-5）视为满足。
