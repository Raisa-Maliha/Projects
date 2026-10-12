from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    rpc_url: str = "https://ethereum-sepolia-rpc.publicnode.com"
    chain_id: int = 11155111
    agent_wallet_private_key: str = ""
    dry_run: bool = True
    generate_demo_wallet: bool = True
    watch_tokens: str = ""

    @property
    def watch_token_list(self) -> list[str]:
        return [t.strip() for t in self.watch_tokens.split(",") if t.strip()]


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
