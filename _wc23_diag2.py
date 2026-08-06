import _remote
c = _remote.connect()
R = _remote.run
R(c, "cat /proc/286546/status | head -12; echo ---; cat /proc/286546/wchan; echo; echo ---; ls -l /proc/286546/task | wc -l; echo '--- children:'; cat /proc/286546/task/286546/children 2>/dev/null; echo; echo '--- stack of py:'; cat /proc/286546/stat | cut -d' ' -f3; echo '--- open fds (locks):'; ls -l /proc/286546/fd 2>/dev/null | tail -20")
R(c, "ls -la /tmp | grep -i -E 'equiv_iso|highmem|mk_' | head -20; ls -la /root/mk_v2_runs/*.lock /tmp/*.lock 2>/dev/null | head")
R(c, "top -b -n1 | head -15")
c.close()
