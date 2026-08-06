import _remote as R

c = R.connect()
R.run(c, "tail -30 '/root/mk_v2_runs/e3_campaign/wave15/_smoke/fidelity/b7/"
         "worker_logs/layernorm.log'", timeout=60)
R.run(c, "tail -5 '/root/mk_v2_runs/e3_campaign/wave15/_smoke/fidelity/b8/"
         "worker_logs/Activation__gelu_bf16.py__round_0_to_round_1__after.log'",
      timeout=60)
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "for l in open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/fidelity/b8/b8_fidelity.jsonl'):\n"
         "    r = json.loads(l)\n"
         "    print(r['task_id'], r['side'], '| expected', r.get('expected_exe_ok'),\n"
         "          '| got', r.get('replicated_exe_ok'), '| err', str(r.get('error'))[:200],\n"
         "          '| mm', r.get('mismatch'))\n"
         "r0 = json.loads(open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl').readline())\n"
         "print('before type:', type(r0['before']).__name__)\n"
         "print('before repr head:', repr(r0['before'])[:200])\n"
         "EOF", timeout=60)
c.close()
print("DONE")
