from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


IntentKind = Literal[
    "query_balance",
    "transfer_native",
    "transfer_erc20",
    "approve_erc20",
    "update_policy",
    "autonomy_cycle",
    "unknown",
]

Decision = Literal["allow", "confirm", "deny"]
TxStatus = Literal["simulated", "queued", "broadcast", "failed", "denied"]


class Policy(BaseModel):
    max_native_per_tx_eth: float = 0.05
    daily_native_cap_eth: float = 0.1
    confirm_above_eth: float = 0.02
    allowlist_enabled: bool = False
    allowlist: list[str] = Field(default_factory=list)
    block_unlimited_approvals: bool = True
    max_gas_gwei: float = 50.0
    cooldown_seconds: int = 15
    autonomous_enabled: bool = True
    max_autonomy_intents_per_cycle: int = 3


class Intent(BaseModel):
    kind: IntentKind
    text: str
    to: str | None = None
    amount_eth: float | None = None
    token: str | None = None
    spender: str | None = None
    policy_patch: dict[str, Any] | None = None
    preview_only: bool = False


class RiskVerdict(BaseModel):
    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    estimated_gas_gwei: float | None = None


class AgentRequest(BaseModel):
    text: str


class PolicyUpdate(BaseModel):
    policy: Policy


class ConfirmRequest(BaseModel):
    activity_id: str


class Activity(BaseModel):
    id: str
    ts: str
    intent: Intent
    verdict: RiskVerdict
    status: TxStatus
    tx_hash: str | None = None
    detail: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
