import asyncio
import logging
from typing import Optional

from config.config_new_bot import (
    ASSETS,
    BALANCE_PERCENT_PER_TRADE,
    CLOB_API,
    DRY_RUN,
    MIN_ARBITRAGE_THRESHOLD,
    MIN_CONTRACTS,
    MIN_SUM_PROBABILITY,
    POLYGON,
    POLYMARKET_PROXY,
    PRIVATE_KEY,
    SCAN_INTERVAL_SECONDS
)
from core.data.price_fetcher import PriceFetcher
from core.market import MarketDiscovery, MarketSessionRunner
from core.trading.arbitrage_calculator import ArbitrageCalculator
from core.trading.state_manager import StateManager
from core.trading.trade_logger import TradeLogger
from core.trading.balance_watcher import BalanceWatcher, fetch_effective_balance_sync
from core.trading.trade_executor import TradeExecutor
from py_clob_client import ClobClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BalancedArbitrageBot")


class BalancedArbitrageBot:
    def __init__(self):
        self.client: Optional[ClobClient] = None
        self.market_discovery = MarketDiscovery(ASSETS)
        self.price_fetcher = PriceFetcher()
        
        balance = self._init_starting_balance()
        self.calculator = ArbitrageCalculator(
            deposit_balance=balance,
            balance_percent_per_trade=float(BALANCE_PERCENT_PER_TRADE),
            min_arbitrage_threshold=float(MIN_ARBITRAGE_THRESHOLD),
            min_sum_probability=float(MIN_SUM_PROBABILITY),
            min_contracts=int(MIN_CONTRACTS),
        )
        self.state_manager = StateManager(balance)
        self.trade_logger = TradeLogger()
        self.executor: Optional[TradeExecutor] = None
        self.balance_watcher: Optional[BalanceWatcher] = None
        
    def _init_starting_balance(self) -> float:
        balance = fetch_effective_balance_sync()
        logger.info(f"Starting balance: ${balance:.2f}")
        return balance
    
    async def initialize_client(self) -> bool:
        try:
            if DRY_RUN:
                logger.info("TEST MODE - Polymarket client is not created")
                self.client = None
                return True
            
            if not PRIVATE_KEY or not POLYMARKET_PROXY:
                logger.error("PRIVATE_KEY or POLYMARKET_PROXY not found")
                return False
            
            self.client = ClobClient(
                host=CLOB_API,
                key=PRIVATE_KEY,
                chain_id=POLYGON,
                signature_type=2,
                funder=POLYMARKET_PROXY
            )
            
            try:
                if hasattr(self.client, "create_or_derive_api_creds"):
                    creds = self.client.create_or_derive_api_creds()
                else:
                    try:
                        creds = self.client.create_api_key()
                    except Exception:
                        creds = self.client.derive_api_key()
                self.client.set_api_creds(creds)
            except Exception as e:
                logger.error(f"Error initializing API credentials: {e}")
                return False
            
            self.executor = TradeExecutor(self.client)
            return True
            
        except Exception as e:
            logger.error(f"Client initialization error: {e}")
            return False
    
    async def run(self):
        if not await self.initialize_client():
            logger.error("Failed to initialize the client")
            return

        if not DRY_RUN:
            self.balance_watcher = BalanceWatcher(
                state_manager=self.state_manager,
                calculator=self.calculator,
            )
            asyncio.create_task(self.balance_watcher.run())

        logger.info("=" * 80)
        logger.info("BOT STARTED")
        logger.info(f"Mode: {'TEST' if DRY_RUN else 'LIVE'}")
        logger.info(f"Deposit: ${self.state_manager.balance:.2f}")
        logger.info(f"Assets: {', '.join(ASSETS)}")
        logger.info("=" * 80)

        while True:
            try:
                market = await self.market_discovery.find_active_market()

                if market:
                    logger.info(f"\n{'=' * 80}")
                    logger.info(f"MARKET FOUND: {market.question}")
                    logger.info(f"{'=' * 80}")

                    if not DRY_RUN:
                        self._refresh_balance_before_market()

                    session_runner = MarketSessionRunner(
                        state_manager=self.state_manager,
                        price_fetcher=self.price_fetcher,
                        calculator=self.calculator,
                        trade_logger=self.trade_logger,
                        executor=self.executor,
                    )
                    await session_runner.run(market)
                else:
                    logger.info("Active market not found, waiting...")
                    await asyncio.sleep(SCAN_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                logger.info("\nStopping bot...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)

    def _refresh_balance_before_market(self) -> None:
        if DRY_RUN:
            return

        new_balance = fetch_effective_balance_sync()
        self.state_manager.initial_balance = new_balance
        self.state_manager.balance = new_balance

        self.calculator.deposit_balance = new_balance

        logger.info(f"Updated starting balance before new session: ${new_balance:.2f}")
