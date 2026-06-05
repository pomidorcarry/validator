"""Quick check: what materials were extracted."""
import json, os
from collections import Counter
from pathlib import Path

elems_dir = Path(__file__).parent / "storage" / "elements"
materials = Counter()
for f in sorted(elems_dir.iterdir()):
    if f.name.endswith("_norm.json"):
        try:
            d = json.loads(f.read_text("utf-8"))
            mat = d.get("material", "")
            if mat:
                materials[mat] += 1
            else:
                materials["(none)"] += 1
        except Exception as e:
            materials[f"(error:{e})"] += 1

for m, c in materials.most_common(20):
    safe = m.encode("utf-8").hex() if m != "(none)" else "(none)"
    print(f"  {safe}: {c}")
