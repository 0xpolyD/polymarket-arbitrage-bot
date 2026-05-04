import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict

logger = logging.getLogger("TradeLogger")


@dataclass
class BalancedTradeEntry:
    entry_id: str                    
    timestamp: str                   
    market_slug: str                 
    market_question: str             

    price_up: float                  
    price_down: float                
    total_probability: float         
    arbitrage_diff: float            
    
    contracts_up: int                
    contracts_down: int              
    
    cost_up: float                   
    cost_down: float                 
    total_cost: float                
    
    k_coefficient: float             
    paper_trade: bool = True        


@dataclass
class MarketSession:
    session_id: str                 
    market_slug: str                 
    market_question: str             
    start_time: str                  
    end_time: Optional[str] = None   
    
    entries: List[Dict] = None       
    
    final_price_up: Optional[float] = None      
    final_price_down: Optional[float] = None    
    final_pnl: Optional[float] = None           
    final_pnl_percent: Optional[float] = None  
    
    paper_mode: bool = True          
    
    def __post_init__(self):
        if self.entries is None:
            self.entries = []


class TradeLogger:
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = logs_dir
        self.current_session: Optional[MarketSession] = None
        self._ensure_logs_dir()
        
        logger.info(f"TradeLogger initialized: {self.logs_dir}")
    
    def _ensure_logs_dir(self):
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
    
    def _get_date_dir(self) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_dir = os.path.join(self.logs_dir, date_str)
        if not os.path.exists(date_dir):
            os.makedirs(date_dir)
        return date_dir
    
    def start_session(self, market_slug: str, market_question: str, paper_mode: bool = True):
        session_id = f"{market_slug}_{int(datetime.now().timestamp())}"
        
        self.current_session = MarketSession(
            session_id=session_id,
            market_slug=market_slug,
            market_question=market_question,
            start_time=datetime.now().isoformat(),
            paper_mode=paper_mode
        )
        
        logger.info(f"Session started: {session_id}")
    
    def log_trade(self, market, opportunity: Dict, paper_mode: bool = True):
        from uuid import uuid4

        if not self.current_session:
            self.start_session(
                market_slug=getattr(market, "slug", "unknown"),
                market_question=getattr(market, "question", ""),
                paper_mode=paper_mode,
            )

        entry = BalancedTradeEntry(
            entry_id=str(uuid4())[:8],
            timestamp=datetime.now().isoformat(),
            market_slug=getattr(market, "slug", "unknown"),
            market_question=getattr(market, "question", ""),
            price_up=float(opportunity.get("up_price", 0)),
            price_down=float(opportunity.get("down_price", 0)),
            total_probability=float(opportunity.get("total_probability", 0)),
            arbitrage_diff=float(opportunity.get("arbitrage_diff", 0)),
            contracts_up=int(opportunity.get("contracts_up", 0)),
            contracts_down=int(opportunity.get("contracts_down", 0)),
            cost_up=float(opportunity.get("bet_up_usdc", 0)),
            cost_down=float(opportunity.get("bet_down_usdc", 0)),
            total_cost=float(opportunity.get("total_bet", 0)),
            k_coefficient=float(opportunity.get("k", 0)),
            paper_trade=paper_mode,
        )

        self.log_entry(entry)
    
    def log_entry(self, entry: BalancedTradeEntry):
        if not self.current_session:
            logger.warning("No active session for entry logging")
            return
        
        self.current_session.entries.append(asdict(entry))
        logger.info(f"Entry logged: {entry.entry_id}")
    
    def end_session(
        self, 
        final_price_up: float, 
        final_price_down: float,
        final_pnl: Optional[float] = None,
        final_pnl_percent: Optional[float] = None
    ):

        if not self.current_session:
            logger.warning("No active session to end")
            return
        
        self.current_session.end_time = datetime.now().isoformat()
        self.current_session.final_price_up = final_price_up
        self.current_session.final_price_down = final_price_down
        self.current_session.final_pnl = final_pnl
        self.current_session.final_pnl_percent = final_pnl_percent
        
        self._save_session()
        
        logger.info(f"Session ended: {self.current_session.session_id}")
        self.current_session = None
    
    def _save_session(self):
        if not self.current_session:
            return
        
        date_dir = self._get_date_dir()
        filename = f"{self.current_session.session_id}.json"
        filepath = os.path.join(date_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.current_session), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Session saved: {filepath}")
        except Exception as e:
            logger.error(f"Error saving session: {e}")
    
    def get_daily_summary(self) -> Dict:
        date_dir = self._get_date_dir()
        total_sessions = 0
        total_entries = 0
        total_pnl = 0.0
        successful_sessions = 0
        
        for filename in os.listdir(date_dir):
            if not filename.endswith('.json') or filename == 'summary.json':
                continue
            
            filepath = os.path.join(date_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    session = json.load(f)
                
                total_sessions += 1
                total_entries += len(session.get('entries', []))
                
                if session.get('final_pnl') is not None:
                    total_pnl += session['final_pnl']
                    if session['final_pnl'] > 0:
                        successful_sessions += 1
            
            except Exception as e:
                logger.error(f"Error reading session {filename}: {e}")
        
        summary = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_sessions": total_sessions,
            "total_entries": total_entries,
            "total_pnl": total_pnl,
            "successful_sessions": successful_sessions,
            "success_rate": successful_sessions / total_sessions if total_sessions > 0 else 0.0
        }
        
        summary_path = os.path.join(date_dir, 'summary.json')
        try:
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving summary: {e}")
        
        return summary
