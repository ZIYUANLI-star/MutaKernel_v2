"""Substantive spot-check of all 9 dead_host_constant proofs.

For each proven probe: locate its mutant record in probe_manifest.json,
re-derive the mutated module-level variable from the mutation site, then list
EVERY reference to that variable in the mutated source with its enclosing
def/class, and independently re-check the rule premise:
  variable assigned at module level, referenced only by get_inputs /
  get_init_inputs (never by Model/ModelNew or helpers they call).
"""
import _remote as R

verify_py = r"""
import ast, json

PROVEN = ["L1_P1__const_perturb__0", "L1_P1__const_perturb__1",
          "L1_P14__const_perturb__0", "L1_P14__const_perturb__1",
          "L1_P21__const_perturb__19", "L1_P6__const_perturb__4",
          "L1_P6__const_perturb__5", "L1_P6__const_perturb__2",
          "L2_P64__const_perturb__25"]

man = json.load(open('/root/mk_v2_runs/e1/probe_manifest.json'))
plist = man if isinstance(man, list) else (man.get('probes') or man.get('mutants') or [])
print('manifest type:', type(man).__name__,
      'keys:' if isinstance(man, dict) else 'len:',
      list(man.keys())[:8] if isinstance(man, dict) else len(man))
probes = {}
for p in plist:
    if isinstance(p, dict):
        pid = p.get('probe_id') or p.get('id')
        if pid:
            probes[pid] = p

for pid in PROVEN:
    p = probes.get(pid)
    print('=' * 72)
    print('probe:', pid, '| manifest keys:', sorted(p.keys()) if p else None)
    if not p:
        continue
    code = p.get('mutated_code') or p.get('mutated_source') or ''
    site = p.get('site') or {}
    line = site.get('line_start') or p.get('line_start')
    if not code:
        print('  NO SOURCE IN MANIFEST; fields:', json.dumps(
            {k: str(v)[:80] for k, v in p.items()}, ensure_ascii=False)[:600])
        continue
    tree = ast.parse(code)
    var = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and node.lineno == line:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    var = t.id
    print('  mutated line', line, '-> variable:', var,
          '| stmt:', code.splitlines()[line-1].strip()[:80] if line else '')
    if not var:
        continue
    # every reference with enclosing scope
    scopes = []
    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = ['<module>']
        def visit_ClassDef(self, n):
            self.stack.append('class ' + n.name); self.generic_visit(n); self.stack.pop()
        def visit_FunctionDef(self, n):
            self.stack.append('def ' + n.name); self.generic_visit(n); self.stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_Name(self, n):
            if n.id == var:
                scopes.append((n.lineno, ' / '.join(self.stack)))
            self.generic_visit(n)
    V().visit(tree)
    for ln, sc in scopes:
        print('   ref line %4d in %s' % (ln, sc))
    bad = [s for _, s in scopes
           if 'get_inputs' not in s and 'get_init_inputs' not in s
           and s != '<module>']
    mod_refs = [ln for ln, s in scopes if s == '<module>']
    # module-level refs other than the assignment itself are suspicious
    extra_mod = [ln for ln in mod_refs if ln != line]
    print('  VERDICT:', 'SOUND' if not bad and not extra_mod else
          'NEEDS_REVIEW bad=%r extra_module_refs=%r' % (bad, extra_mod))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_proof_verify.py", "w") as fh:
    fh.write(verify_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _proof_verify.py",
      timeout=300)
c.close()
print("PROOF_VERIFY_DONE")
