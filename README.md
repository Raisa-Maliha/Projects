# Agent Wallet

Autonomous on-chain wallet agent: natural-language intents, policy-gated execution, asset views, and an audit log.

The agent never signs a transaction until the **risk engine** allows it. High-value or ambiguous actions stay queued for confirmation.

## What it does

| Layer | Role |
| --- | --- |
| Planner | Turns chat commands into structured intents (`transfer`, `approve`, `query`, `policy`) |
| Risk control | Per-tx caps, daily spend, allowlists, unlimited-approval ban, gas ceiling, cooldown |
| Execution | Simulates first, then signs and broadcasts (or dry-runs) on EVM |
| Asset management | Native + ERC-20 balances, activity, spend ledger |
| Autonomy | Queued intents can auto-execute when they pass policy |

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

With the default `.env`, the agent uses an **ephemeral demo wallet** and **dry-run** mode (no real broadcasts). To execute on Sepolia:

1. Put a funded testnet key in `AGENT_WALLET_PRIVATE_KEY`
2. Set `DRY_RUN=false`
3. Keep caps tight in the Risk panel

Never use a mainnet key with real funds for a demo.

## Example commands

- `what's my balance`
- `send 0.01 ETH to 0x...`
- `preview send 5 USDC to 0x...` (needs a token in `WATCH_TOKENS`)
- `set daily cap to 0.05 ETH`
- `allow 0x...`
- `run autonomy cycle`

## API

- `GET /api/wallet` — address, chain, dry-run flag
- `GET /api/balances` — native + watched tokens
- `GET /api/policy` / `PUT /api/policy`
- `POST /api/agent/intent` — `{ "text": "send 0.01 ETH to 0x..." }`
- `POST /api/agent/autonomy` — drain the queue under policy
- `GET /api/activity`

## Safety model

1. Parse intent (no signing)
2. Simulate / estimate
3. Evaluate policy (allow / confirm / deny)
4. Sign only on **allow**, or after you confirm a queued item
5. Append an immutable-style JSON activity record
