import os
from dotenv import load_dotenv

load_dotenv()

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
PAPER_BALANCE = float(os.getenv("PAPER_BALANCE", "200.0"))
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLYMARKET_PROXY = os.getenv("POLYMARKET_PROXY")

CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"
WS_ENDPOINT = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
POLYGON = 137  

POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL")
USDC_CONTRACT_ADDRESS = os.getenv(
    "USDC_CONTRACT_ADDRESS",
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  
)

ASSETS = os.getenv("ASSETS", "btc,eth").lower().split(",")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ORDER_TIMEOUT_SECONDS = float(os.getenv("ORDER_TIMEOUT_SECONDS", "60"))

BALANCE_PERCENT_PER_TRADE = float(os.getenv("BALANCE_PERCENT_PER_TRADE", "0.10"))  
MIN_ARBITRAGE_THRESHOLD = float(os.getenv("MIN_ARBITRAGE_THRESHOLD", "0.02"))      
MIN_SUM_PROBABILITY = float(os.getenv("MIN_SUM_PROBABILITY", "0.975"))           
MIN_CONTRACTS = int(os.getenv("MIN_CONTRACTS", "5"))                               
MAX_POSITIONS_SIMULTANEOUSLY = 1      
SCAN_INTERVAL_SECONDS = 0.2        
MONITORING_DURATION_MINUTES = 15      

PRICE_ADJUSTMENT_TICK = float(os.getenv("PRICE_ADJUSTMENT_TICK", "0.02"))
TICK_ACTIVATION_THRESHOLD = float(os.getenv("TICK_ACTIVATION_THRESHOLD", "0.65"))

MAX_TOTAL_EXPOSURE_PERCENT = 0.20      
MIN_LIQUIDITY_REQUIREMENT = 1000       

DETAILED_LOGGING = True                
SAVE_RESULTS_TO_FILE = True            

USE_DYNAMIC_POSITION_SIZING = False     
MIN_PROFIT_TARGET_USD = 5.0            
MAX_SLIPPAGE_PERCENT = 0.5             

SIMULATE_EXECUTION = True               
RANDOM_PRICE_NOISE = 0.001            

def validate_config():
    errors = []
    
    if BALANCE_PERCENT_PER_TRADE <= 0 or BALANCE_PERCENT_PER_TRADE > 1:
        errors.append("BALANCE_PERCENT_PER_TRADE must be between 0 and 1")
    
    if MIN_ARBITRAGE_THRESHOLD <= 0 or MIN_ARBITRAGE_THRESHOLD > 0.1:
        errors.append("MIN_ARBITRAGE_THRESHOLD must be between 0 and 0.1")
    
    if MIN_SUM_PROBABILITY <= 0 or MIN_SUM_PROBABILITY >= 1:
        errors.append("MIN_SUM_PROBABILITY must be between 0 and 1")
    
    if MAX_TOTAL_EXPOSURE_PERCENT <= 0 or MAX_TOTAL_EXPOSURE_PERCENT > 1:
        errors.append("MAX_TOTAL_EXPOSURE_PERCENT must be between 0 and 1")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(errors))
    
    return True

if __name__ != "__main__":
    validate_config()
    
    print("Balanced arbitrage bot configuration loaded:")
    print(f"  Deposit: ${PAPER_BALANCE}")
    print(f"  Trade size: {BALANCE_PERCENT_PER_TRADE:.1%}")
    print(f"  Minimum arbitrage: {MIN_ARBITRAGE_THRESHOLD:.1%}")
    print(f"  Mode: {'TEST' if DRY_RUN else 'LIVE'}")
