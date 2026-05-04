import logging
from datetime import datetime
from typing import Optional
from core.models import MarketInfo, OrderBook

logger = logging.getLogger("StateManager")


class Position:    
    def __init__(self):
        self.contracts_up = 0      
        self.contracts_down = 0    
        self.cost_up = 0.0          
        self.cost_down = 0.0        
        self.entry_price_up = 0.0   
        self.entry_price_down = 0.0  
        self.total_cost = 0.0       
        self.entry_time = None       
        
    @property
    def is_active(self) -> bool:
        return self.contracts_up > 0 or self.contracts_down > 0


class StateManager:
    def __init__(self, initial_balance: float):
        self.position = Position()
        self.market: Optional[MarketInfo] = None
        self.order_book: Optional[OrderBook] = None
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.entry_history = []  
        
        logger.info(f"StateManager initialized with balance ${initial_balance:.2f}")
    
    def reset_for_new_market(self):
        self.position = Position()
        self.order_book = None
        self.balance = self.initial_balance 
    
    def enter_position(
        self, 
        contracts_up: int,
        contracts_down: int,
        price_up: float,
        price_down: float
    ):
        cost_up = price_up * float(contracts_up)
        cost_down = price_down * float(contracts_down)
        total_cost = cost_up + cost_down
        
        if total_cost > self.balance:
            logger.error(f"Insufficient funds: need ${total_cost:.2f}, available ${self.balance:.2f}")
            return False
        
        old_contracts_up = self.position.contracts_up
        old_contracts_down = self.position.contracts_down
        old_cost_up = self.position.cost_up
        old_cost_down = self.position.cost_down
        
        new_total_contracts_up = old_contracts_up + contracts_up
        new_total_contracts_down = old_contracts_down + contracts_down
        
        new_total_cost_up = old_cost_up + cost_up
        new_total_cost_down = old_cost_down + cost_down
        new_total_cost = new_total_cost_up + new_total_cost_down
        
        if new_total_contracts_up > 0:
            avg_price_up = new_total_cost_up / float(new_total_contracts_up)
        else:
            avg_price_up = 0.0
        
        if new_total_contracts_down > 0:
            avg_price_down = new_total_cost_down / float(new_total_contracts_down)
        else:
            avg_price_down = 0.0
        
        self.position.contracts_up = new_total_contracts_up
        self.position.contracts_down = new_total_contracts_down
        self.position.cost_up = new_total_cost_up
        self.position.cost_down = new_total_cost_down
        self.position.entry_price_up = avg_price_up
        self.position.entry_price_down = avg_price_down
        self.position.total_cost = new_total_cost
        
        if self.position.entry_time is None:
            self.position.entry_time = datetime.now()
        
        self.balance -= total_cost
        
        entry = {
            "time": datetime.now(),
            "market": self.market.question if self.market else "Unknown",
            "contracts_up": contracts_up,
            "contracts_down": contracts_down,
            "price_up": float(price_up),
            "price_down": float(price_down),
            "total_cost": float(total_cost)
        }
        self.entry_history.append(entry)
        
        logger.info(f"Entering position: UP={contracts_up}×${price_up:.3f}, DOWN={contracts_down}×${price_down:.3f}, Total=${total_cost:.2f}")
        logger.info(f"Accumulated position: UP={new_total_contracts_up}, DOWN={new_total_contracts_down}, Average price UP=${avg_price_up:.3f}, DOWN=${avg_price_down:.3f}")
        return True
    
    def close_position(self, final_price_up: float, final_price_down: float):
        if not self.position.is_active:
            logger.warning("No active position to close")
            return None
        
        final_value_up = final_price_up * float(self.position.contracts_up)
        final_value_down = final_price_down * float(self.position.contracts_down)
        total_final_value = final_value_up + final_value_down
        
        pnl = total_final_value - self.position.total_cost
        pnl_percent = (pnl / self.position.total_cost) * 100.0
        
        self.balance += total_final_value
        
        result = {
            "entry_time": self.position.entry_time,
            "close_time": datetime.now(),
            "entry_price_up": float(self.position.entry_price_up),
            "entry_price_down": float(self.position.entry_price_down),
            "final_price_up": float(final_price_up),
            "final_price_down": float(final_price_down),
            "contracts_up": self.position.contracts_up,
            "contracts_down": self.position.contracts_down,
            "total_cost": float(self.position.total_cost),
            "final_value": float(total_final_value),
            "pnl": float(pnl),
            "pnl_percent": float(pnl_percent)
        }
        
        logger.info(f"Position closed: PnL=${pnl:.2f} ({pnl_percent:.2f}%)")
        
        self.position = Position()
        
        return result
    
    def get_position_summary(self) -> dict:
        return {
            "is_active": self.position.is_active,
            "contracts_up": self.position.contracts_up,
            "contracts_down": self.position.contracts_down,
            "cost_up": float(self.position.cost_up),
            "cost_down": float(self.position.cost_down),
            "entry_price_up": float(self.position.entry_price_up),
            "entry_price_down": float(self.position.entry_price_down),
            "total_cost": float(self.position.total_cost),
            "balance": float(self.balance),
            "entry_time": self.position.entry_time.isoformat() if self.position.entry_time else None
        }
    
    def get_balance_info(self) -> dict:
        used = self.initial_balance - self.balance
        used_percent = (used / self.initial_balance) * 100.0 if self.initial_balance > 0 else 0.0
        
        return {
            "initial": float(self.initial_balance),
            "current": float(self.balance),
            "used": float(used),
            "used_percent": float(used_percent),
            "available": float(self.balance)
        }
