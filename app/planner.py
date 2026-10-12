from __future__ import annotations

import re

from app.models import Intent

ADDR = re.compile(r"0x[a-fA-F0-9]{40}")
AMOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*(eth|ether|wei)?", re.I)


def parse_intent(text: str) -> Intent:
    raw = text.strip()
    lower = raw.lower()
    preview = lower.startswith("preview ") or "simulate" in lower or "dry run" in lower
    cleaned = re.sub(r"^(preview|simulate)\s+", "", lower)

    if any(k in cleaned for k in ("balance", "portfolio", "holdings", "what do i have")):
        return Intent(kind="query_balance", text=raw, preview_only=preview)

    if "autonomy" in cleaned or "run agent" in cleaned or "drain queue" in cleaned:
        return Intent(kind="autonomy_cycle", text=raw, preview_only=preview)

    policy_patch = _policy_patch(cleaned)
    if policy_patch:
        return Intent(kind="update_policy", text=raw, policy_patch=policy_patch, preview_only=preview)

    addrs = ADDR.findall(raw)
    amount = _amount(cleaned)

    if "approve" in cleaned:
        token = addrs[0] if addrs else None
        spender = addrs[1] if len(addrs) > 1 else (addrs[0] if addrs else None)
        return Intent(
            kind="approve_erc20",
            text=raw,
            token=token,
            spender=spender,
            amount_eth=amount,
            preview_only=preview,
        )

    if any(k in cleaned for k in ("send", "transfer", "pay", "move")):
        to = addrs[0] if addrs else None
        token = addrs[1] if len(addrs) > 1 else None
        kind = "transfer_erc20" if "usdc" in cleaned or "token" in cleaned or token else "transfer_native"
        return Intent(
            kind=kind,
            text=raw,
            to=to,
            token=token,
            amount_eth=amount,
            preview_only=preview,
        )

    if addrs and amount is not None:
        return Intent(kind="transfer_native", text=raw, to=addrs[0], amount_eth=amount, preview_only=preview)

    return Intent(kind="unknown", text=raw, preview_only=preview)


def _amount(text: str) -> float | None:
    m = AMOUNT.search(text)
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or "eth").lower()
    if unit == "wei":
        return value / 1e18
    return value


def _policy_patch(text: str) -> dict | None:
    patch: dict = {}
    if "allowlist off" in text or "disable allowlist" in text:
        patch["allowlist_enabled"] = False
    if "allowlist on" in text or "enable allowlist" in text:
        patch["allowlist_enabled"] = True
    m = re.search(r"daily cap(?: to)?\s+(\d+(?:\.\d+)?)", text)
    if m:
        patch["daily_native_cap_eth"] = float(m.group(1))
    m = re.search(r"(?:max|per[- ]tx)(?: cap)?(?: to)?\s+(\d+(?:\.\d+)?)", text)
    if m and "daily" not in text:
        patch["max_native_per_tx_eth"] = float(m.group(1))
    m = ADDR.search(text)
    if m and ("allow " in text or "whitelist" in text or "allowlist" in text):
        patch["allow_address"] = m.group(0)
    if "autonomy on" in text or "enable autonomy" in text:
        patch["autonomous_enabled"] = True
    if "autonomy off" in text or "disable autonomy" in text:
        patch["autonomous_enabled"] = False
    return patch or None
