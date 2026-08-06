cd /root/mk_v2
ls
echo '--- subdirs ---'
find /root/mk_v2 -maxdepth 3 -type d -not -path '*/.git*' -not -path '*/KernelBench*' -not -path '*__pycache__*' | head -40
echo '--- worker/falsify ---'
find /root/mk_v2 -maxdepth 4 -name '_mutant_worker.py' -o -maxdepth 4 -name 'run_e1_cse_falsify.py' | head
echo '--- stress ---'
grep -rl 'sparse_extreme' /root/mk_v2 --include='*.py' | head -20
