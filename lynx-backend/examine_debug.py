"""Examine the debug AI output and figure out why AI returns 0 problems."""

import json

with open('debug_ai_output2.txt', encoding='utf-8') as f:
    content = f.read()

sections = content.split('=' * 60)

print(f"Total sections: {len(sections)}")
print()

# Section 0: empty (header before first ===)
# Section 1: SYSTEM PROMPT
# Section 2: REQUIREMENTS CHECKLIST
# Section 3: ELEMENTS SUMMARY
# Section 4: TZ SUMMARY
# Section 5: Full user prompt length (info)
# Section 6: AI RESPONSE

# Examine REQUIREMENTS CHECKLIST
print("=" * 40)
print("REQUIREMENTS CHECKLIST:")
print("=" * 40)
req_lines = sections[2].strip().split('\n')
for line in req_lines[:30]:
    print(line)
print("...")
print()

# Examine ELEMENTS SUMMARY - look at system names, materials
print("=" * 40)
print("ELEMENTS SUMMARY (systems/materials):")
print("=" * 40)
elem_lines = sections[3].strip().split('\n')
for line in elem_lines:
    stripped = line.strip()
    if stripped and ('материал' in stripped.lower() or 'material' in stripped.lower() or 'систем' in stripped.lower() or 'system' in stripped.lower() or 'pipe' in stripped.lower() or 'диаметр' in stripped.lower() or 'steel' in stripped.lower() or 'ppr' in stripped.lower() or 'hppe' in stripped.lower() or 'pex' in stripped.lower()):
        print(f"  {stripped}")
print(f"  Total lines in elements section: {len(elem_lines)}")
print()

# Examine TZ SUMMARY - check if PEX requirement is there
print("=" * 40)
print("TZ SUMMARY:")
print("=" * 40)
tz_lines = sections[4].strip().split('\n')
# Find lines about materials
for i, line in enumerate(tz_lines):
    if i < 5:
        print(line)
    stripped = line.strip()
    if stripped and ('материал' in stripped.lower() or 'material' in stripped.lower() or 'труб' in stripped.lower() or 'pipe' in stripped.lower() or 'изоляц' in stripped.lower() or 'диаметр' in stripped.lower()):
        print(f"  >>> {stripped}")
print(f"  Total lines in TZ section: {len(tz_lines)}")
print()

# Examine AI RESPONSE
print("=" * 40)
print("AI RESPONSE:")
print("=" * 40)
resp_lines = sections[6].strip().split('\n') if len(sections) > 6 else ['(no response section)']
for line in resp_lines:
    print(line)
print()

# Also check the raw prompt file
print("=" * 40)
print("FULL PROMPT ANALYSIS:")
print("=" * 40)
with open('debug_full_prompt.txt', encoding='utf-8') as f:
    prompt = f.read()
print(f"Full prompt length: {len(prompt)} chars")
print(f"Last 300 chars: ...{prompt[-300:]}")
