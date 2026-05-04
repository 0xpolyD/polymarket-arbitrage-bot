import asyncio
import logging
from typing import Dict, List
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, PostOrdersArgs
from py_clob_client.order_builder.constants import BUY
from core.models import MarketInfo
from config.config_new_bot import DRY_RUN

logger = logging.getLogger("TradeExecutor")


class TradeExecutor:    
    def __init__(self, client: ClobClient):
        self.client = client
        logger.info(f"TradeExecutor initialized (DRY_RUN={DRY_RUN})")
    
    async def warmup_market(self, market: MarketInfo) -> None:
        """Pre-initialize client for market.

        Creates one dummy order for each leg so that
        py-clob-client fetches tick-size / neg-risk / fee-rate once
        and caches these values before the first real trade.
        Orders are NOT sent to exchange, only create_order is executed.
        """

        try:
            loop = asyncio.get_running_loop()

            dummy_up = OrderArgs(
                token_id=market.token_id_yes,
                price=0.5,
                size=1.0,
                side=BUY,
            )

            dummy_down = OrderArgs(
                token_id=market.token_id_no,
                price=0.5,
                size=1.0,
                side=BUY,
            )

            await asyncio.gather(
                loop.run_in_executor(None, self.client.create_order, dummy_up),
                loop.run_in_executor(None, self.client.create_order, dummy_down),
            )

            logger.info(
                "Market pre-initialization completed (warmup), slug=%s",
                getattr(market, "slug", "unknown"),
            )

        except Exception as e:
            logger.warning(f"Error warmup_market for market {getattr(market, 'slug', 'unknown')}: {e}")

    async def execute_balanced_trade(
        self, 
        market: MarketInfo, 
        opportunity: Dict
    ) -> bool:
    
        try:
            logger.debug(
                "OPPORTUNITY | market=%s | UP=%.3f DOWN=%.3f | UPx%d=$%.2f DOWNx%d=$%.2f | TOTAL=$%.2f",
                getattr(market, "slug", "unknown"),
                float(opportunity.get("up_price", 0.0)),
                float(opportunity.get("down_price", 0.0)),
                int(opportunity.get("contracts_up", 0)),
                float(opportunity.get("bet_up_usdc", 0.0)),
                int(opportunity.get("contracts_down", 0)),
                float(opportunity.get("bet_down_usdc", 0.0)),
                float(opportunity.get("total_bet", 0.0)),
            )
            
            if DRY_RUN:
                logger.info("TEST MODE - trades are not executed")
                return True
            else:
                return await self._execute_real_trade(market, opportunity)
                
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return False
    
    async def _execute_real_trade(
        self, 
        market: MarketInfo, 
        opportunity: Dict
    ) -> bool:
        
        try:
            loop = asyncio.get_running_loop()

            adj_up_price = float(opportunity['up_price'])
            adj_down_price = float(opportunity['down_price'])

            up_args = OrderArgs(
                token_id=market.token_id_yes,
                price=adj_up_price,
                size=float(opportunity['contracts_up']),
                side=BUY,
            )

            down_args = OrderArgs(
                token_id=market.token_id_no,
                price=adj_down_price,
                size=float(opportunity['contracts_down']),
                side=BUY,
            )

            up_signed, down_signed = await asyncio.gather(
                loop.run_in_executor(None, self.client.create_order, up_args),
                loop.run_in_executor(None, self.client.create_order, down_args)
            )

            batch_orders = [
                PostOrdersArgs(order=up_signed, orderType=OrderType.GTC),
                PostOrdersArgs(order=down_signed, orderType=OrderType.GTC),
            ]

            return await self._execute_batch_orders(
                batch_orders,
                market,
                opportunity,
            )
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return False
    
    async def _execute_batch_orders(
        self,
        orders: List[PostOrdersArgs],
        market: MarketInfo,
        opportunity: Dict
    ) -> bool:
          
            
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, self.client.post_orders, orders)

            if not isinstance(results, list) or len(results) != 2:
                logger.error(f"Expected 2 results, got: {results}")
                return False

            def _get(obj, key, default=None):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            def _is_success(resp) -> bool:
                status = str(_get(resp, "status", "")).lower()
                order_id = _get(resp, "orderID") or _get(resp, "order_id")
                if not order_id:
                    return False
                if status in ("error", "rejected", "cancelled"):
                    return False
                return True

            up_resp, down_resp = results[0], results[1]
            up_success = _is_success(up_resp)
            down_success = _is_success(down_resp)

            if up_success and down_success:
                logger.info("✓ Paired entry executed successfully (BATCH)")
                logger.info(
                    f"  UP: {opportunity['contracts_up']} contracts at ${opportunity['up_price']:.3f}"
                )
                logger.info(
                    f"  DOWN: {opportunity['contracts_down']} contracts at ${opportunity['down_price']:.3f}"
                )
                return True

            if up_success or down_success:
                logger.warning("Partial batch execution - attempting to rollback orders")
                await self._rollback_partial_fill(results)
            else:
                logger.warning("Unsuccessful batch execution - both orders rejected/cancelled")

            return False
                
        except Exception as e:
            logger.error(f"Error in batch orders: {e}")
            return False

    async def _rollback_partial_fill(self, results: List) -> None:
        logger.info("Rolling back partially filled orders...")

        for i, result in enumerate(results):
            if isinstance(result, dict):
                status = str(result.get("status", "")).lower()
                order_id = result.get("orderID") or result.get("order_id")
            else:
                status = str(getattr(result, "status", "")).lower()
                order_id = getattr(result, "orderID", None) or getattr(result, "order_id", None)

            if not order_id or status in ("cancelled", "error", "rejected"):
                continue

            side = "UP" if i == 0 else "DOWN"
            logger.info(f"Cancelling {side} order: {order_id}")
            await self._cancel_order(order_id)

    async def _cancel_order(self, order_id: str) -> bool:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.client.cancel, order_id)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
