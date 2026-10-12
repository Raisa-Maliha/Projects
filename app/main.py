from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent import WalletAgent
from app.models import AgentRequest, ConfirmRequest, Policy
from app.store import list_activity, load_policy, save_policy

STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Agent Wallet", version="0.1.0")
agent = WalletAgent()

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "agent-wallet"}


@app.get("/api/wallet")
def wallet():
    return agent.snapshot()


@app.get("/api/balances")
def balances():
    return agent.snapshot()


@app.get("/api/policy")
def get_policy():
    return load_policy()


@app.put("/api/policy")
def put_policy(policy: Policy):
    return save_policy(policy)


@app.get("/api/activity")
def activity():
    return list_activity()


@app.post("/api/agent/intent")
def intent(req: AgentRequest):
    if not req.text.strip():
        raise HTTPException(400, "text is required")
    return _dump(agent.handle_text(req.text))


@app.post("/api/agent/confirm")
def confirm(req: ConfirmRequest):
    return _dump(agent.confirm(req.activity_id))


@app.post("/api/agent/autonomy")
def autonomy():
    return {"results": [_dump(r) for r in agent.run_autonomy()]}


def _dump(result: dict) -> dict:
    out = dict(result)
    if "activity" in out and hasattr(out["activity"], "model_dump"):
        out["activity"] = out["activity"].model_dump()
    if "policy" in out and hasattr(out["policy"], "model_dump"):
        out["policy"] = out["policy"].model_dump()
    if "wallet" in out:
        pass
    if "results" in out:
        out["results"] = [_dump(r) if isinstance(r, dict) else r for r in out["results"]]
    return out
