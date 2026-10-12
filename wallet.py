from eth_account import Account
from eth_account.signers.local import LocalAccount

from app.config import settings

Account.enable_unaudited_hdwallet_features()


class AgentKey:
    def __init__(self) -> None:
        key = (settings.agent_wallet_private_key or "").strip()
        if key:
            if not key.startswith("0x"):
                key = "0x" + key
            self.account: LocalAccount = Account.from_key(key)
            self.ephemeral = False
        elif settings.generate_demo_wallet:
            self.account = Account.create()
            self.ephemeral = True
        else:
            raise RuntimeError("No AGENT_WALLET_PRIVATE_KEY and GENERATE_DEMO_WALLET is false")

    @property
    def address(self) -> str:
        return self.account.address
