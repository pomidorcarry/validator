"""Count and identify sections in debug output."""
with open('debug_ai_output2.txt', encoding='utf-8') as f:
    c = f.read()
n = c.count('=' * 60)
print(f"Found {n} divider lines")
sections = c.split('=' * 60)
for i, s in enumerate(sections):
    lines = s.strip().split('\n')
    h = lines[0][:80] if lines else '(empty)'
    safe_h = ''.join(ch if ord(ch) < 128 else f'[U+{ord(ch):04X}]' for ch in h)
    print(f"  Section {i}: {len(s)} chars, header={safe_h}")
