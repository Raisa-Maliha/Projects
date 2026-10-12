from __future__ import annotations

from app.chain import Chain
from app.config import settings
from app.models import Activity, Intent, Policy, RiskVerdict
from app.planner import parse_intent
from app.risk import evaluate
from app.store import (
    append_activity,
    get_activity,
    load_policy,
    native_spent_today,
    new_id,
    queued_intents,
    record_native_spend,
    save_policy,
    stamp,
    update_activity,
)
from app.wallet import AgentKey


class WalletAgent:
    def __init__(self) -> None:
        self.key = AgentKey()
        self.chain = Chain()

    def snapshot(self) -> dict:
        address = self.key.address
        native = 0.0
        tokens = []
        error = None
        try:
            native = self.chain.native_balance_eth(address)
            for token in settings.watch_token_list:
                tokens.append(self.chain.token_snapshot(token, address))
        except Exception as exc:
            error = str(exc)
        return {
            "address": address,
            "ephemeral": self.key.ephemeral,
            "dry_run": settings.dry_run,
            "online": self.chain.online,
            "chain_id": self.chain.chain_id(),
            "rpc_url": settings.rpc_url,
            "native_eth": native,
            "tokens": tokens,
            "spent_today_eth": native_spent_today(),
            "error": error,
        }

    def handle_text(self, text: str) -> dict:
        intent = parse_intent(text)
        policy = load_policy()
        return self.execute_intent(intent, policy, confirmed=False)

    def execute_intent(self, intent: Intent, policy: Policy, confirmed: bool) -> dict:
        gas = self.chain.gas_gwei()
        verdict = evaluate(intent, policy, gas)

        if intent.kind == "query_balance":
            snap = self.snapshot()
            activity = self._log(intent, verdict, "simulated", "Balance query")
            return {"ok": True, "message": self._balance_message(snap), "activity": activity, "wallet": snap}

        if intent.kind == "update_policy":
            updated = self._apply_policy(policy, intent.policy_patch or {})
            activity = self._log(intent, verdict, "simulated", "Policy updated")
            return {"ok": True, "message": "Risk policy updated.", "activity": activity, "policy": updated}

        if intent.kind == "autonomy_cycle":
            results = self.run_autonomy(policy)
            activity = self._log(intent, verdict, "simulated", f"Autonomy cycle ran {len(results)} queued item(s)")
            return {"ok": True, "message": f"Autonomy cycle processed {len(results)} item(s).", "results": results, "activity": activity}

        if intent.kind == "approve_erc20":
            activity = self._log(intent, verdict, "denied" if verdict.decision == "deny" else "queued", "; ".join(verdict.reasons))
            if verdict.decision == "deny":
                return {"ok": False, "message": activity.detail, "activity": activity}
            return {
                "ok": True,
                "message": "Approval intents are parsed and risk-checked; ERC-20 send path is native-first in this demo.",
                "activity": activity,
            }

        if intent.kind == "transfer_erc20":
            activity = self._log(intent, verdict, "denied" if verdict.decision == "deny" else "queued", "; ".join(verdict.reasons))
            return {
                "ok": verdict.decision != "deny",
                "message": "ERC-20 transfer is queued for a watched token; native ETH transfers execute in this build.",
                "activity": activity,
            }

        if intent.kind != "transfer_native":
            activity = self._log(intent, verdict, "denied", "Unsupported intent")
            return {"ok": False, "message": "I can query balances, move ETH, update policy, or run autonomy.", "activity": activity}

        if verdict.decision == "deny":
            activity = self._log(intent, verdict, "denied", "; ".join(verdict.reasons))
            return {"ok": False, "message": "Risk engine denied this transfer.", "activity": activity}

        if verdict.decision == "confirm" and not confirmed and not intent.preview_only:
            activity = self._log(intent, verdict, "queued", "Waiting for human confirmation")
            return {
                "ok": True,
                "needs_confirm": True,
                "message": "Queued for confirmation (above risk threshold).",
                "activity": activity,
            }

        return self._send_native(intent, verdict)

    def confirm(self, activity_id: str) -> dict:
        item = get_activity(activity_id)
        if not item or item.status != "queued":
            return {"ok": False, "message": "No queued activity with that id"}
        policy = load_policy()
        return self.execute_intent(item.intent, policy, confirmed=True)

    def run_autonomy(self, policy: Policy | None = None) -> list[dict]:
        policy = policy or load_policy()
        if not policy.autonomous_enabled:
            return [{"ok": False, "message": "Autonomy is disabled in policy"}]
        out = []
        for item in queued_intents()[: policy.max_autonomy_intents_per_cycle]:
            verdict = evaluate(item.intent, policy, self.chain.gas_gwei())
            if verdict.decision != "allow":
                out.append({"id": item.id, "ok": False, "message": "Still blocked: " + "; ".join(verdict.reasons)})
                continue
            result = self._send_native(item.intent, verdict)
            update_activity(
                item.model_copy(
                    update={
                        "status": result["activity"].status,
                        "tx_hash": result["activity"].tx_hash,
                        "detail": "Autonomy executed: " + result["activity"].detail,
                    }
                )
            )
            out.append(result)
        return out

    def _send_native(self, intent: Intent, verdict: RiskVerdict) -> dict:
        assert intent.to and intent.amount_eth is not None
        try:
            tx = self.chain.build_native_tx(self.key.address, intent.to, intent.amount_eth)
            sim = self.chain.simulate_native(tx)
            if intent.preview_only:
                activity = self._log(intent, verdict, "simulated", f"Preview only. {sim}")
                return {"ok": True, "message": f"Simulation succeeded. {sim}", "activity": activity, "tx": _public_tx(tx)}
            tx_hash, mode = self.chain.sign_and_send(self.key.account, tx, settings.dry_run)
            status = "simulated" if settings.dry_run or not self.chain.online else "broadcast"
            if status in ("broadcast", "simulated"):
                record_native_spend(intent.amount_eth)
            activity = self._log(intent, verdict, status, f"{mode}. {sim}", tx_hash)
            return {
                "ok": True,
                "message": f"Transfer {status}: {intent.amount_eth} ETH → {intent.to}",
                "activity": activity,
                "tx": _public_tx(tx),
            }
        except Exception as exc:
            activity = self._log(intent, verdict, "failed", str(exc))
            return {"ok": False, "message": f"Execution failed: {exc}", "activity": activity}

    def _apply_policy(self, policy: Policy, patch: dict) -> Policy:
        data = policy.model_dump()
        extra_allow = patch.pop("allow_address", None)
        data.update({k: v for k, v in patch.items() if k in data})
        if extra_allow:
            data["allowlist_enabled"] = True
            if extra_allow not in data["allowlist"]:
                data["allowlist"].append(extra_allow)
        return save_policy(Policy.model_validate(data))

    def _log(self, intent: Intent, verdict: RiskVerdict, status, detail: str, tx_hash: str | None = None) -> Activity:
        activity = Activity(
            id=new_id(),
            ts=stamp(),
            intent=intent,
            verdict=verdict,
            status=status,
            tx_hash=tx_hash,
            detail=detail,
        )
        return append_activity(activity)

    def _balance_message(self, snap: dict) -> str:
        bits = [f"Address {snap['address']}", f"{snap['native_eth']:.6f} ETH on chain {snap['chain_id']}"]
        for t in snap["tokens"]:
            bits.append(f"{t['balance']} {t['symbol']}")
        if snap.get("error"):
            bits.append(f"(RPC note: {snap['error']})")
        if snap["ephemeral"]:
            bits.append("Ephemeral demo key — do not fund with real assets.")
        return " · ".join(bits)


def _public_tx(tx: dict) -> dict:
    return {
        "to": tx.get("to"),
        "value_wei": str(tx.get("value")),
        "gas": tx.get("gas"),
        "chainId": tx.get("chainId"),
        "nonce": tx.get("nonce"),
    }
