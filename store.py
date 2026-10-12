from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import DATA_DIR
from app.models import Activity, Policy, utc_now

POLICY_PATH = DATA_DIR / "policy.json"
ACTIVITY_PATH = DATA_DIR / "activity.json"
SPEND_PATH = DATA_DIR / "spend.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_policy() -> Policy:
    raw = _read_json(POLICY_PATH, None)
    return Policy.model_validate(raw) if raw else Policy()


def save_policy(policy: Policy) -> Policy:
    _write_json(POLICY_PATH, policy.model_dump())
    return policy


def list_activity(limit: int = 50) -> list[Activity]:
    items = _read_json(ACTIVITY_PATH, [])
    return [Activity.model_validate(i) for i in items][:limit]


def append_activity(activity: Activity) -> Activity:
    items = _read_json(ACTIVITY_PATH, [])
    items.insert(0, activity.model_dump())
    _write_json(ACTIVITY_PATH, items[:200])
    return activity


def get_activity(activity_id: str) -> Activity | None:
    for item in list_activity(200):
        if item.id == activity_id:
            return item
    return None


def update_activity(activity: Activity) -> Activity:
    items = _read_json(ACTIVITY_PATH, [])
    for i, row in enumerate(items):
        if row.get("id") == activity.id:
            items[i] = activity.model_dump()
            break
    _write_json(ACTIVITY_PATH, items)
    return activity


def queued_intents() -> list[Activity]:
    return [a for a in list_activity(200) if a.status == "queued"]


def record_native_spend(amount_eth: float) -> None:
    ledger = _read_json(SPEND_PATH, {"days": {}})
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ledger.setdefault("days", {})
    ledger["days"][day] = float(ledger["days"].get(day, 0)) + amount_eth
    _write_json(SPEND_PATH, ledger)


def native_spent_today() -> float:
    ledger = _read_json(SPEND_PATH, {"days": {}})
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return float(ledger.get("days", {}).get(day, 0))


def last_broadcast_ts() -> str | None:
    for item in list_activity(50):
        if item.status in ("broadcast", "simulated") and item.intent.kind.startswith("transfer"):
            return item.ts
    return None


def new_id() -> str:
    return uuid4().hex[:12]


def stamp() -> str:
    return utc_now()
