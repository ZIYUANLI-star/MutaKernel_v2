import json
controls = json.load(open('/root/mk_v2_runs/e1/original_controls.json'))
print('total controls:', len(controls))
for name, v in controls.items():
    st = v.get('status')
    if st != 'survived':
        print('=====', name, '->', st, '| reason_class:', v.get('reason_class'))
        err = str(v.get('error') or '')
        print('  err:', err[:400])
        for t in (v.get('trials') or [])[:3]:
            print('  trial', t.get('trial'), t.get('status'), '|', str(t.get('reason'))[:250])
