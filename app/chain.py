from __future__ import annotations

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from app.config import settings

ERC20_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "symbol",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "transfer",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
]


class Chain:
    def __init__(self) -> None:
        self.w3 = Web3(Web3.HTTPProvider(settings.rpc_url, request_kwargs={"timeout": 20}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.online = False
        try:
            self.online = self.w3.is_connected()
        except Exception:
            self.online = False

    def chain_id(self) -> int:
        if self.online:
            try:
                return self.w3.eth.chain_id
            except Exception:
                pass
        return settings.chain_id

    def native_balance_eth(self, address: str) -> float:
        if not self.online:
            return 0.0
        wei = self.w3.eth.get_balance(Web3.to_checksum_address(address))
        return float(self.w3.from_wei(wei, "ether"))

    def gas_gwei(self) -> float:
        if not self.online:
            return 1.0
        return float(self.w3.from_wei(self.w3.eth.gas_price, "gwei"))

    def token_snapshot(self, token: str, owner: str) -> dict:
        addr = Web3.to_checksum_address(token)
        owner_cs = Web3.to_checksum_address(owner)
        c = self.w3.eth.contract(address=addr, abi=ERC20_ABI)
        decimals = int(c.functions.decimals().call())
        symbol = c.functions.symbol().call()
        raw = int(c.functions.balanceOf(owner_cs).call())
        return {
            "address": addr,
            "symbol": symbol,
            "decimals": decimals,
            "balance": raw / (10**decimals),
            "raw": str(raw),
        }

    def build_native_tx(self, from_addr: str, to: str, amount_eth: float) -> dict:
        nonce = 0
        gas_price = self.w3.to_wei(1, "gwei")
        if self.online:
            nonce = self.w3.eth.get_transaction_count(Web3.to_checksum_address(from_addr))
            gas_price = self.w3.eth.gas_price
        tx = {
            "from": Web3.to_checksum_address(from_addr),
            "to": Web3.to_checksum_address(to),
            "value": self.w3.to_wei(amount_eth, "ether"),
            "nonce": nonce,
            "gas": 21_000,
            "gasPrice": gas_price,
            "chainId": self.chain_id(),
        }
        return tx

    def simulate_native(self, tx: dict) -> str:
        if not self.online:
            return "offline-sim: native transfer would be sent"
        try:
            self.w3.eth.call(
                {
                    "from": tx["from"],
                    "to": tx["to"],
                    "value": tx["value"],
                }
            )
            return "eth_call ok"
        except Exception as exc:
            msg = str(exc)
            if "OutOfFunds" in msg or "insufficient" in msg.lower():
                return f"simulation warning: sender cannot fund this tx ({msg})"
            raise

    def sign_and_send(self, account, tx: dict, dry_run: bool) -> tuple[str, str]:
        signed = account.sign_transaction(tx)
        raw = signed.raw_transaction
        tx_hash = signed.hash.hex()
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        if dry_run or not self.online:
            return tx_hash, "dry-run (not broadcast)"
        sent = self.w3.eth.send_raw_transaction(raw)
        return sent.hex(), "broadcast"
