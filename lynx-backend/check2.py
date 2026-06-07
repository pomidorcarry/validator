import json, os, sqlite3
from collections import Counter

m = Counter()
conn = sqlite3.connect('lynx.db')
cur = conn.cursor()
cur.execute("SELECT id FROM elements WHERE model_version_id = 'cae2d778-78ea-4f42-a2d8-b80713f6aaef'")
v12_ids = set(r[0] for r in cur.fetchall())
conn.close()

elems_dir = 'storage/elements'
for fid in v12_ids:
    f = os.path.join(elems_dir, fid + '_norm.json')
    if os.path.exists(f):
        d = json.load(open(f, encoding='utf-8'))
        mat = d.get('material', '')
        if mat:
            m[mat] += 1
        else:
            m['(none)'] += 1

for mat, cnt in m.most_common(15):
    safe = mat.encode('utf-8').hex() if mat != '(none)' else '(none)'
    print(f'{cnt:5d} | {safe}')
