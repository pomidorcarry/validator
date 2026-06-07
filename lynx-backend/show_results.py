"""Show AI check results from debug output."""
import json

with open('debug_ai_output2.txt', encoding='utf-8') as f:
    content = f.read()

sections = content.split('=' * 60)

# Read AI RESPONSE section
resp_lines = sections[6].strip().split('\n')
try:
    problems = json.loads(resp_lines[0])
except:
    problems = []
    for line in resp_lines:
        print(repr(line))

if problems:
    for p in problems:
        print(json.dumps(p, ensure_ascii=False, indent=2))
        print("---")

# Also check debug_ai_check.log for AI response
import os, re
if os.path.exists('debug_ai_check.log'):
    with open('debug_ai_check.log', encoding='utf-8', errors='replace') as f:
        log = f.read()
    # Find "AI RESPONSE:" section
    m = re.search(r'AI RESPONSE:(-{10,}.*?)(?:=== END LOG|$)', log, re.DOTALL)
    if m:
        resp_raw = m.group(1).strip()
        print("=" * 40)
        print("FULL AI RESPONSE FROM LOG:")
        print("=" * 40)
        # Extract JSON from markdown blocks
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n\s*```', resp_raw, re.DOTALL)
        if json_match:
            print(json_match.group(1)[:2000])
        else:
            print(resp_raw[:2000])
