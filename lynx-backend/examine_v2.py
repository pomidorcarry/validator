"""Examine debug output using only ASCII-safe output."""

import re

with open('debug_ai_output2.txt', encoding='utf-8') as f:
    content = f.read()

sections = content.split('=' * 60)

def safe(text, maxlen=200):
    """Replace non-ASCII with escaped hex."""
    result = []
    for c in text[:maxlen]:
        if ord(c) < 128 and c not in '\r':
            result.append(c)
        elif c in '\n\t':
            result.append(c)
        else:
            result.append(f'\\u{ord(c):04x}')
    return ''.join(result)

# Examine REQUIREMENTS CHECKLIST
print("=== REQUIREMENTS CHECKLIST ===")
req_lines = sections[2].strip().split('\n')
for line in req_lines:
    print(safe(line, 200))
print()

# Examine ELEMENTS SUMMARY - look for system/pipe/diameter/material lines
print("=== ELEMENTS SUMMARY (system+diameter+material lines) ===")
elem_lines = sections[3].strip().split('\n')
for line in elem_lines:
    low = line.lower()
    if any(kw in low for kw in ['system', 'dimeter', 'material', 'pipe', '\\u0441\\u0438\\u0441\\u0442\\u0435\\u043c', '\\u043c\\u0430\\u0442\\u0435\\u0440\\u0438\\u0430\\u043b', '\\u0434\\u0438\\u0430\\u043c\\u0435\\u0442\\u0440', '\\u0442\\u0440\\u0443\\u0431', 'steel', 'ppr', 'hdpe', 'pex', 'poly']):
        print(safe(line, 300))
print(f"  Total lines in elements: {len(elem_lines)}")
print()

# Examine AI RESPONSE
print("=== AI RESPONSE ===")
if len(sections) > 6:
    resp = sections[6].strip()
    print(safe(resp, 5000))
else:
    print("(no response section)")
# Also look for AI response in sections 5 (the info line) or raw
print()

# Also search for where the prompt ends and AI response begins
# The AI chat function runs after generating the prompt
# Let's look at the debug_ai_check.log
import os
if os.path.exists('debug_ai_check.log'):
    with open('debug_ai_check.log', encoding='utf-8', errors='replace') as f:
        log_content = f.read()
    # Find AI RESPONSE
    idx = log_content.find('AI RESPONSE')
    if idx >= 0:
        print("=== AI RESPONSE FROM LOG ===")
        print(safe(log_content[idx:idx+3000], 3000))
    else:
        print("(AI RESPONSE not found in log, showing last 1000 chars)")
        print(safe(log_content[-1000:], 1000))
else:
    print("(debug_ai_check.log not found)")
