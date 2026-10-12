from __future__ import annotations

from datetime import datetime, timezone

from app.models import Intent, Policy, RiskVerdict
from app.store import last_broadcast_ts, native_spent_today


UNLIMITED = 2**256 - 1


def evaluate(intent: Intent, policy: Policy, gas_gwei: float) -> RiskVerdict:
    reasons: list[str] = []
    decision = "allow"

    if intent.kind == "unknown":
        return RiskVerdict(decision="deny", reasons=["Could not parse a safe on-chain intent"], estimated_gas_gwei=gas_gwei)

    if intent.kind in ("query_balance", "update_policy", "autonomy_cycle"):
        return RiskVerdict(decision="allow", reasons=["Read/policy action — no funds move"], estimated_gas_gwei=gas_gwei)

    if intent.kind in ("transfer_native", "transfer_erc20") and not intent.to:
        return RiskVerdict(decision="deny", reasons=["Missing recipient address"], estimated_gas_gwei=gas_gwei)

    if intent.kind.startswith("transfer") and (intent.amount_eth is None or intent.amount_eth <= 0):
        return RiskVerdict(decision="deny", reasons=["Amount must be greater than 0"], estimated_gas_gwei=gas_gwei)

    amount = float(intent.amount_eth or 0)

    if intent.kind == "transfer_native":
        if amount > policy.max_native_per_tx_eth:
            reasons.append(f"Amount {amount} ETH exceeds per-tx cap {policy.max_native_per_tx_eth}")
            decision = "deny"
        spent = native_spent_today()
        if spent + amount > policy.daily_native_cap_eth:
            reasons.append(f"Daily cap {policy.daily_native_cap_eth} ETH would be exceeded (spent {spent})")
            decision = "deny"
        if amount >= policy.confirm_above_eth and decision != "deny":
            decision = "confirm"
            reasons.append(f"Amount is at/above confirm threshold {policy.confirm_above_eth} ETH")

    if policy.allowlist_enabled and intent.to:
        allowed = {a.lower() for a in policy.allowlist}
        if intent.to.lower() not in allowed:
            reasons.append("Recipient is not on the allowlist")
            decision = "deny"

    if intent.to and intent.to.lower() == "0x" + "0" * 40:
        reasons.append("Zero address is blocked")
        decision = "deny"

    if intent.kind == "approve_erc20" and policy.block_unlimited_approvals:
        if intent.amount_eth is None or intent.amount_eth >= UNLIMITED / 1e18:
            reasons.append("Unlimited ERC-20 approvals are blocked by policy")
            decision = "deny"

    if gas_gwei > policy.max_gas_gwei:
        reasons.append(f"Gas {gas_gwei:.2f} gwei exceeds ceiling {policy.max_gas_gwei}")
        decision = "deny"

    last = last_broadcast_ts()
    if last and intent.kind.startswith("transfer") and decision != "deny":
        try:
            last_dt = datetime.fromisoformat(last)
            delta = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if delta < policy.cooldown_seconds:
                reasons.append(f"Cooldown {policy.cooldown_seconds}s still active")
                decision = "deny"
        except ValueError:
            pass

    if not reasons and decision == "allow":
        reasons.append("Passed per-tx, daily, gas, and allowlist checks")

    return RiskVerdict(decision=decision, reasons=reasons, estimated_gas_gwei=gas_gwei)
