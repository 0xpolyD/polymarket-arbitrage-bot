import asyncio
import logging
from typing import Optional
from config.config_new_bot import (
    DRY_RUN,
    PAPER_BALANCE,
    POLYGON_RPC_URL,
    POLYMARKET_PROXY,
    USDC_CONTRACT_ADDRESS,
)
from core.trading.state_manager import StateManager
from core.trading.arbitrage_calculator import ArbitrageCalculator

logger = logging.getLogger("BalanceWatcher")

try:  
    from web3 import Web3  
except ImportError:  
    Web3 = None  


def fetch_effective_balance_sync() -> float:
    paper_balance = float(PAPER_BALANCE)

    if DRY_RUN:
        logger.info(f"[Balance] DRY_RUN: using PAPER_BALANCE=${paper_balance:.2f}")
        return paper_balance

    if Web3 is None or not POLYGON_RPC_URL or not POLYMARKET_PROXY:
        logger.info(
            f"[Balance] Web3/RPC/PROXY not configured, using PAPER_BALANCE=${paper_balance:.2f}"
        )
        return paper_balance

    try:
        w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))  
        if not w3.is_connected():
            logger.warning("[Balance] Failed to connect to Polygon RPC, using PAPER_BALANCE")
            logger.info(f"[Balance] PAPER_BALANCE=${paper_balance:.2f}")
            return paper_balance

        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
        ]

        contract = w3.eth.contract(
            address=w3.to_checksum_address(USDC_CONTRACT_ADDRESS), abi=erc20_abi
        )
        raw_balance = contract.functions.balanceOf(
            w3.to_checksum_address(POLYMARKET_PROXY)
        ).call()
        decimals = contract.functions.decimals().call()
        usdc_balance = raw_balance / (10 ** decimals)

        logger.info(
            f"[Balance] On-chain USDC on {POLYMARKET_PROXY}: ${usdc_balance:.6f}"
        )
        return float(usdc_balance)
    except Exception as e:  
        logger.warning(f"[Balance] Web3 error, using PAPER_BALANCE: {e}")
        logger.info(f"[Balance] PAPER_BALANCE=${paper_balance:.2f}")
        return paper_balance


class BalanceWatcher:
    def __init__(
        self,
        state_manager: StateManager,
        calculator: ArbitrageCalculator,
        interval_seconds: float = 300.0,
    ) -> None:
        self.state_manager = state_manager
        self.calculator = calculator
        self.interval_seconds = interval_seconds
        self._last_balance: Optional[float] = None

    async def run(self) -> None:

        if DRY_RUN:
            logger.info("[BalanceWatcher] DRY_RUN - balance watcher not started")
            return

        loop = asyncio.get_running_loop()

        while True:
            try:
                new_balance = await loop.run_in_executor(
                    None, fetch_effective_balance_sync
                )

                if self._last_balance is None or new_balance != self._last_balance:
                    self.state_manager.initial_balance = new_balance
                    self.state_manager.balance = new_balance
                    self.calculator.deposit_balance = new_balance

                    logger.info(
                        f"[BalanceWatcher] Balance updated: ${self._last_balance or 0:.2f} -> ${new_balance:.2f}"
                    )
                    self._last_balance = new_balance

            except Exception as e: 
                logger.error(f"[BalanceWatcher] Error updating balance: {e}")

            await asyncio.sleep(self.interval_seconds)
