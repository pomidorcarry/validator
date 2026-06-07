"""Extract the actual AI response JSON from section 12."""
with open('debug_ai_output2.txt', encoding='utf-8') as f:
    c = f.read()
sections = c.split('=' * 60)
resp_raw = sections[12].strip()

# Write the raw response to a file
with open('ai_raw_response.txt', 'w', encoding='utf-8') as out:
    out.write(resp_raw)

print(f"Raw response length: {len(resp_raw)}")
print(f"First 100 chars: {resp_raw[:100]}")
print(f"Last 100 chars: {resp_raw[-100:]}")
