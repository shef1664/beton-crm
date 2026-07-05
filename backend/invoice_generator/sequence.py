import json
from pathlib import Path


def next_invoice_number(state_path: Path) -> str:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    current_number = 1
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        current_number = int(state.get("next_number", 1))

    state_path.write_text(json.dumps({"next_number": current_number + 1}, ensure_ascii=False), encoding="utf-8")
    return str(current_number)

