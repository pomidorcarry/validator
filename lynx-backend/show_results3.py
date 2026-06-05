"""Save AI check results to a text file that can be read."""
import json, re, os

with open('debug_ai_output2.txt', encoding='utf-8') as f:
    content = f.read()

sections = content.split('=' * 60)
resp_raw = sections[6].strip()

json_match = re.search(r'```(?:json)?\s*\n*(.*?)\n*\s*```', resp_raw, re.DOTALL)
if json_match:
    json_str = json_match.group(1).strip()
else:
    json_str = resp_raw.strip()

try:
    problems = json.loads(json_str)
except:
    start = json_str.find('[')
    end = json_str.rfind(']')
    if start >= 0 and end > start:
        json_str = json_str[start:end+1]
        try:
            problems = json.loads(json_str)
        except:
            problems = None
    else:
        problems = None

with open('results_summary.txt', 'w', encoding='utf-8') as out:
    if problems is None:
        out.write("Could not parse JSON\n")
        out.write(f"Raw resp first 1000:\n{json_str[:1000]}\n")
    else:
        out.write(f"Total problems: {len(problems)}\n\n")
        for p in problems:
            out.write(json.dumps(p, ensure_ascii=False, indent=2) + "\n")
            out.write("---\n")

    # Also log raw response
    out.write("\n\n=== RAW RESPONSE ===\n")
    out.write(resp_raw[:3000])

    # Check log
    if os.path.exists('debug_ai_check.log'):
        with open('debug_ai_check.log', encoding='utf-8', errors='replace') as f:
            log = f.read()
        r_start = log.find('RAW AI RESPONSE:')
        if r_start >= 0:
            out.write("\n\n=== RAW AI RESPONSE FROM LOG ===\n")
            out.write(log[r_start:r_start+2000])
        p_start = log.find('PROMPT:')
        if p_start >= 0:
            out.write("\n\n=== PROMPT FROM LOG ===\n")
            out.write(log[p_start:p_start+3000])

print("Written to results_summary.txt")
