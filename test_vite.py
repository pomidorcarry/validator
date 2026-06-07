import urllib.request

urls = [
    'http://127.0.0.1:8080/src/main.js',
    'http://127.0.0.1:8080/src/viewer.js',
    'http://127.0.0.1:8080/src/viewer.js?v=1',
]
for u in urls:
    try:
        r = urllib.request.urlopen(u)
        body = r.read().decode('utf-8', errors='replace')
        name = u.split('/')[-1].split('?')[0]
        print(f'{name}: HTTP {r.status}, len={len(body)}')
        if 'error' in body.lower():
            for i, line in enumerate(body.split('\n')):
                if 'error' in line.lower() and 'Error' in line:
                    print(f'  L{i}: {line.strip()[:150]}')
    except Exception as e:
        print(f'{u}: FAIL - {e}')
print('=== Done ===')
