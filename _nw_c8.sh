for p in 270127 270128 276614 276615 108720 280179; do
  echo "--- $p"
  ps -o pid=,ppid=,stat=,etime=,cmd= -p $p 2>/dev/null || echo "gone"
  awk '/^State:|^PPid:/' /proc/$p/status 2>/dev/null
done
echo '=== init children sample ==='
ps -o pid=,ppid=,stat=,cmd= --ppid 1 2>/dev/null | head -20
