import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

import aiohttp

from config.config_new_bot import (
    SCAN_INTERVAL_SECONDS,
    WS_ENDPOINT,
    DRY_RUN
)
from core.models import MarketInfo, OrderBook, OrderBookEntry
from core.trading.arbitrage_calculator import ArbitrageCalculator
from core.trading.state_manager import StateManager
from core.trading.trade_executor import TradeExecutor
from core.trading.trade_logger import TradeLogger
from core.data.price_fetcher import PriceFetcher

logger = logging.getLogger("MarketSession")

PRICE_WINDOW_DELTA = 1e-6


class MarketSessionRunner:
    def __init__(
        self,
        state_manager: StateManager,
        price_fetcher: PriceFetcher,
        calculator: ArbitrageCalculator,
        trade_logger: TradeLogger,
        executor: Optional[TradeExecutor] = None,
    ) -> None:
        self.state_manager = state_manager
        self.price_fetcher = price_fetcher
        self.calculator = calculator
        self.trade_logger = trade_logger
        self.executor: Optional[TradeExecutor] = executor

        self.order_book: Optional[OrderBook] = None
        self.is_executing_trade: bool = False
        self.last_trade_time: float = 0.0
        self.window_anchor_up: Optional[float] = None
        self.window_anchor_down: Optional[float] = None
        self.window_trades_count: int = 0

    async def run(self, market: MarketInfo) -> None:
        self.state_manager.market = market
        self.state_manager.reset_for_new_market()
        self.order_book = OrderBook()
        self.window_anchor_up = None
        self.window_anchor_down = None
        self.window_trades_count = 0

        trade_count = 0
        last_scan_log_time: float = 0.0

        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"Token IDs: YES={market.token_id_yes}, NO={market.token_id_no}")

                if not DRY_RUN and self.executor is not None:
                    await self.executor.warmup_market(market)

                async with session.ws_connect(
                    WS_ENDPOINT,
                    ssl=False,
                    timeout=10,
                    heartbeat=20,
                    autoping=True,
                ) as ws:
                    logger.info("WebSocket connected successfully")

                    await ws.send_json({
                        "type": "market",
                        "assets_ids": [market.token_id_yes, market.token_id_no],
                    })

                    while True:
                        try:
                            now_utc = datetime.now(timezone.utc)
                            ttl = max(0, (market.expiration - now_utc).total_seconds())
                            if ttl <= 120:  
                                logger.info("TTL < 120s - ending market monitoring")
                                break

                            msg = await asyncio.wait_for(ws.receive(), timeout=3.0)

                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)

                                if isinstance(data, dict):
                                    await self._process_price_update(market, data)

                                    if self.order_book:
                                        raw_up_price = self.order_book.yes_asks[0].price if self.order_book.yes_asks else None
                                        raw_down_price = self.order_book.no_asks[0].price if self.order_book.no_asks else None

                                        if raw_up_price is None or raw_down_price is None:
                                            continue

                                        up_price = float(raw_up_price)
                                        down_price = float(raw_down_price)
                                        total_prob = up_price + down_price

                                        now_ts = datetime.now().timestamp()
                                        if now_ts - last_scan_log_time >= SCAN_INTERVAL_SECONDS:
                                            last_scan_log_time = now_ts

                                            ttl_minutes = int(ttl // 60)
                                            ttl_seconds = int(ttl % 60)
                                            logger.info(
                                                f"SCAN | TTL: {ttl_minutes}m{ttl_seconds}s | "
                                                f"UP: {up_price:.3f} DOWN: {down_price:.3f} "
                                                f"SUM: {total_prob:.3f}"
                                            )

                                        self.calculator.deposit_balance = self.state_manager.balance
                                        opportunity = self.calculator.calculate_opportunity(up_price, down_price)

                                        if opportunity and self.calculator.validate_opportunity(opportunity):
                                            op_up = opportunity["up_price"]
                                            op_down = opportunity["down_price"]

                                            if self.window_anchor_up is None or self.window_anchor_down is None:
                                                self.window_anchor_up = op_up
                                                self.window_anchor_down = op_down
                                                self.window_trades_count = 0
                                            else:
                                                same_window = (
                                                    abs(op_up - self.window_anchor_up) <= PRICE_WINDOW_DELTA
                                                    and abs(op_down - self.window_anchor_down) <= PRICE_WINDOW_DELTA
                                                )
                                                if not same_window:
                                                    self.window_anchor_up = op_up
                                                    self.window_anchor_down = op_down
                                                    self.window_trades_count = 0

                                            if self.window_trades_count >= 2:
                                                logger.info("The trade limit for the current arbitrage window has been reached, the trade has been skipped.")
                                                continue

                                            if self.is_executing_trade:
                                                continue

                                            required = opportunity["total_bet"]
                                            available = self.state_manager.balance
                                            if required > available:
                                                logger.warning(
                                                    f"Insufficient funds for the transaction: ${required:.2f}, ${available:.2f}"
                                                )
                                                continue

                                            self.is_executing_trade = True
                                            logger.info("Scanning paused, executing the transaction...")

                                            try:
                                                success = True
                                                if not DRY_RUN and self.executor is not None:
                                                    success = await self.executor.execute_balanced_trade(market, opportunity)

                                                if success:
                                                    trade_count += 1
                                                    self.state_manager.enter_position(
                                                        contracts_up=opportunity["contracts_up"],
                                                        contracts_down=opportunity["contracts_down"],
                                                        price_up=opportunity["up_price"],
                                                        price_down=opportunity["down_price"],
                                                    )

                                                    self.trade_logger.log_trade(
                                                        market=market,
                                                        opportunity=opportunity,
                                                        paper_mode=DRY_RUN,
                                                    )

                                                    logger.info(f"Trade #{trade_count} completed")

                                                    self.window_trades_count += 1

                                                    self.last_trade_time = datetime.now().timestamp()
                                                    await asyncio.sleep(5.2)

                                            finally:
                                                self.is_executing_trade = False

                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                logger.warning("WebSocket closed or error")
                                break

                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.error(f"Error in WebSocket loop: {e}")
                            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"WebSocket URL: {WS_ENDPOINT}")
            logger.error(f"Market token IDs: YES={market.token_id_yes}, NO={market.token_id_no}")
            logger.info(f"aiohttp version: {aiohttp.__version__}")

        await self._end_session(market, trade_count)

    async def _process_price_update(self, market: MarketInfo, data: Dict) -> None:
        if not self.order_book:
            self.order_book = OrderBook()

        for change in data.get("price_changes", []):
            if not isinstance(change, dict):
                continue

            side = change.get("side")
            try:
                price = float(change.get("price", 0))
                size = float(change.get("size", 0))
            except Exception:
                continue

            asset_id = change.get("asset_id")
            if not price or not asset_id:
                continue

            entry = OrderBookEntry(price=price, size=size)

            if asset_id == market.token_id_yes:
                if side == "SELL":
                    self.order_book.yes_asks = [entry]
                else:
                    self.order_book.yes_bids = [entry]
            elif asset_id == market.token_id_no:
                if side == "SELL":
                    self.order_book.no_asks = [entry]
                else:
                    self.order_book.no_bids = [entry]

    async def _end_session(self, market: MarketInfo, trade_count: int) -> None:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"MARKET ENDING: {market.question}")
        logger.info(f"{'=' * 80}")

        try:
            prices = await self.price_fetcher.get_prices(market)

            if self.state_manager.position.is_active:
                position = self.state_manager.get_position_summary()

                logger.info(f"Trades executed: {trade_count}")
                logger.info("Accumulated position:")
                logger.info(f"  UP: {position['contracts_up']} contracts at average ${position['entry_price_up']:.3f}")
                logger.info(f"  DOWN: {position['contracts_down']} contracts at average ${position['entry_price_down']:.3f}")
                logger.info(f"  Total cost: ${position['total_cost']:.2f}")

                if prices:
                    logger.info(f"Current prices: UP=${prices['up']:.3f}, DOWN=${prices['down']:.3f}")
            else:
                logger.info("No position was opened")

        except Exception as e:
            logger.error(f"Error ending session: {e}")

        logger.info(f"{'=' * 80}\n")
