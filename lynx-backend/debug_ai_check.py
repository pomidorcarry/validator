"""Debug: Run AI check and show prompt + response."""
import sys, json, asyncio
from pathlib import Path

sys.path.insert(0, Path(__file__).parent.as_posix())

OUT = Path(__file__).parent / "debug_ai_output2.txt"

PROJECT_ID = "3b56bc97-598f-4e5c-93ae-3be451464739"

async def main():
    from app.db.base import init_db
    await init_db()

    from app.db.crud import get_project_tz, get_elements as db_get_elements
    from app.db.models import list_all_models

    models = await list_all_models(project_id=PROJECT_ID)
    processed = [m for m in models if m.get("status") == "processed"]

    all_elements = []
    for m in processed:
        elems = await db_get_elements(m["id"])
        all_elements.extend(elems)

    tz_data = await get_project_tz(PROJECT_ID)

    from app.services.ai.ai_check import _build_requirements_checklist, _summarize_elements, _summarize_tz, SYSTEM_PROMPT

    requirements = _build_requirements_checklist(tz_data)
    elements_summary = _summarize_elements(all_elements)
    tz_summary = _summarize_tz(tz_data)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("SYSTEM PROMPT:\n")
        f.write("=" * 60 + "\n")
        f.write(SYSTEM_PROMPT + "\n\n")

        f.write("=" * 60 + "\n")
        f.write("REQUIREMENTS CHECKLIST:\n")
        f.write("=" * 60 + "\n")
        f.write(requirements + "\n\n")

        f.write("=" * 60 + "\n")
        f.write("ELEMENTS SUMMARY:\n")
        f.write("=" * 60 + "\n")
        f.write(elements_summary + "\n\n")

        f.write("=" * 60 + "\n")
        f.write("TZ SUMMARY:\n")
        f.write("=" * 60 + "\n")
        f.write(tz_summary + "\n\n")

        f.write("=" * 60 + "\n")
        f.write(f"Full user prompt length: {len(requirements) + len(elements_summary) + len(tz_summary)}\n")
        f.write("=" * 60 + "\n\n")

    from app.services.ai.ai_check import run_ai_check as _run
    problems = await _run(PROJECT_ID, all_elements, tz_data)

    with open(OUT, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"AI RESPONSE: {len(problems)} problems\n")
        f.write("=" * 60 + "\n")
        if problems:
            for p in problems:
                f.write(json.dumps(p, ensure_ascii=False, indent=2) + "\n\n")
        else:
            f.write("(empty — no problems found)\n")

    # Also log prompt to separate file for inspection
    full_prompt = f"{SYSTEM_PROMPT}\n\n=== USER PROMPT ===\n\n{requirements}\n\n{elements_summary}\n\n{tz_summary}"
    with open(Path(__file__).parent / "debug_full_prompt.txt", "w", encoding="utf-8") as f:
        f.write(full_prompt)

    print(f"Done. Output written to {OUT}")
    print(f"Problems found: {len(problems)}")

asyncio.run(main())
