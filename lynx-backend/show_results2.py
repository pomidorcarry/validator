"""Show AI check results in ASCII-safe format."""
import json, re, os

with open('debug_ai_output2.txt', encoding='utf-8') as f:
    content = f.read()

sections = content.split('=' * 60)
resp_raw = sections[6].strip()

# Try to extract JSON array from the response
# First try to find it between markdown fences
json_match = re.search(r'```(?:json)?\s*\n*(.*?)\n*\s*```', resp_raw, re.DOTALL)
if json_match:
    json_str = json_match.group(1).strip()
else:
    # Try direct JSON parse
    json_str = resp_raw.strip()

try:
    problems = json.loads(json_str)
except:
    # Try to find [ at start, ] at end
    start = json_str.find('[')
    end = json_str.rfind(']')
    if start >= 0 and end > start:
        json_str = json_str[start:end+1]
        problems = json.loads(json_str)
    else:
        problems = None

if problems is None:
    print("Could not parse JSON from response")
    print(f"First 500 chars of raw: {json_str[:500]}")
else:
    print(f"Total problems: {len(problems)}")
    for p in problems:
        # Safe display: replace non-ASCII with hex
        msg = ''.join(c if ord(c) < 128 or c in '\n\t' else f'[{ord(c):04x}]' for c in p.get('message', ''))
        det = ''.join(c if ord(c) < 128 or c in '\n\t' else f'[{ord(c):04x}]' for c in p.get('details', ''))
        print(f"\n  rule_key: {p.get('rule_key')}")
        print(f"  severity: {p.get('severity')}")
        print(f"  element_ids: {p.get('element_ids')}")
        print(f"  message: {msg[:300]}")
        print(f"  details: {det[:500]}")
        print(f"  ---")

# Also extract from log
if os.path.exists('debug_ai_check.log'):
    with open('debug_ai_check.log', encoding='utf-8', errors='replace') as f:
        log = f.read()
    print("\n\n=== AI RAW RESPONSE FROM LOG ===")
    # Find PROMPT section
    p_start = log.find('PROMPT:')
    r_start = log.find('RAW AI RESPONSE:')
    if r_start >= 0:
        raw = log[r_start:]
        raw = raw[:2000]
        # Safe
        safe = ''.join(c if ord(c) < 128 or c in '\n\t' else f'[{ord(c):04x}]' for c in raw)
        print(safe)
    if p_start >= 0:
        raw = log[p_start:p_start+2000]
        safe = ''.join(c if ord(c) < 128 or c in '\n\t' else f'[{ord(c):04x}]' for c in raw)
        print("\n=== PROMPT ===")
        print(safe)
