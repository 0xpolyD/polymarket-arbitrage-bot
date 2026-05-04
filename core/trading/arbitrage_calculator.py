import logging
from typing import Optional, Dict
from config.config_new_bot import PRICE_ADJUSTMENT_TICK, TICK_ACTIVATION_THRESHOLD

logger = logging.getLogger("ArbitrageCalculator")


class ArbitrageCalculator:
    def __init__(
        self,
        deposit_balance: float,
        balance_percent_per_trade: float = 0.10,
        min_arbitrage_threshold: float = 0.01,
        min_sum_probability: float = 0.975,
        min_contracts: int = 5
    ):
        self.deposit_balance = deposit_balance
        self.balance_percent_per_trade = balance_percent_per_trade
        self.min_arbitrage_threshold = min_arbitrage_threshold
        self.min_sum_probability = min_sum_probability
        self.min_contracts = min_contracts
    
    def calculate_opportunity(
        self, 
        up_price: float, 
        down_price: float
    ) -> Optional[Dict]:

        base_up_price = float(up_price)
        base_down_price = float(down_price)
        max_price = max(base_up_price, base_down_price)

        adj_up_price = base_up_price
        adj_down_price = base_down_price
        tick = float(PRICE_ADJUSTMENT_TICK)
        if tick > 0 and max_price >= TICK_ACTIVATION_THRESHOLD:
            if base_down_price > base_up_price:
                adj_up_price = max(0.0, base_up_price - tick)
                adj_down_price = min(1.0, base_down_price + tick)
            else:  
                adj_up_price = min(1.0, base_up_price + tick)
                adj_down_price = max(0.0, base_down_price - tick)

        up_price = adj_up_price
        down_price = adj_down_price

        total_probability = up_price + down_price
        
        arbitrage_diff = 1.0 - total_probability

        if total_probability >= 1.0:
            logger.debug(f"No arbitrage: {total_probability:.3f} >= 1.00")
            return None

        if total_probability < self.min_sum_probability:
            logger.debug(f"Sum of prices too low: {total_probability:.3f} < {self.min_sum_probability:.3f}")
            return None
        
        if arbitrage_diff < self.min_arbitrage_threshold:
            logger.debug(f"Arbitrage too small: {arbitrage_diff:.3f} < {self.min_arbitrage_threshold:.3f}")
            return None
        
        total_bet = self.deposit_balance * self.balance_percent_per_trade
        
        k = total_bet / total_probability
        
        bet_up_usdc = k * up_price
        bet_down_usdc = k * down_price
        
        contracts_up = int(bet_up_usdc / up_price)
        contracts_down = int(bet_down_usdc / down_price)
        
        if contracts_up < self.min_contracts or contracts_down < self.min_contracts:
            min_bet_up = up_price * float(self.min_contracts)
            min_bet_down = down_price * float(self.min_contracts)
            min_total_bet = min_bet_up + min_bet_down
            
            if min_total_bet > self.deposit_balance:
                logger.warning(f"Insufficient funds for minimum trade: need ${min_total_bet:.2f}, available ${self.deposit_balance:.2f}")
                return None
            
            contracts_up = self.min_contracts
            contracts_down = self.min_contracts
            bet_up_usdc = up_price * float(contracts_up)
            bet_down_usdc = down_price * float(contracts_down)
            total_bet = bet_up_usdc + bet_down_usdc
            
            logger.info(f"Adjusted to minimum contracts: {self.min_contracts}")
        
        opportunity = {
            "up_price": up_price,
            "down_price": down_price,
            "total_probability": total_probability,
            "arbitrage_diff": arbitrage_diff,
            "total_bet": total_bet,
            "k": k,
            "bet_up_usdc": bet_up_usdc,
            "bet_down_usdc": bet_down_usdc,
            "contracts_up": contracts_up,
            "contracts_down": contracts_down
        }
        
        logger.info(f"Opportunity found: arbitrage={arbitrage_diff:.3f}, contracts UP={contracts_up}, DOWN={contracts_down}")
        
        return opportunity
    
    def validate_opportunity(self, opportunity: Dict) -> bool:
        return (
            opportunity["contracts_up"]   >= self.min_contracts and
            opportunity["contracts_down"] >= self.min_contracts and
            opportunity["total_bet"]      <= self.deposit_balance and
            opportunity["arbitrage_diff"] >= self.min_arbitrage_threshold
        )
