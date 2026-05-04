from datetime import datetime
from typing import List
from dataclasses import dataclass, field


@dataclass
class OrderBookEntry:
    price: float
    size: float


@dataclass
class OrderBook:
    yes_bids: List[OrderBookEntry] = field(default_factory=list)
    yes_asks: List[OrderBookEntry] = field(default_factory=list)
    no_bids: List[OrderBookEntry] = field(default_factory=list)
    no_asks: List[OrderBookEntry] = field(default_factory=list)


@dataclass
class MarketInfo:
    slug: str
    question: str
    asset: str
    token_id_yes: str
    token_id_no: str
    end_date_iso: str
    description: str = ""
    
    @property
    def expiration(self) -> datetime:
        return datetime.fromisoformat(self.end_date_iso.replace('Z', '+00:00'))
