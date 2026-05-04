# Balanced Arbitrage Bot for Polymarket

## Project Structure

```
new_bot/
├── core/                           # Core components
│   ├── __init__.py
│   ├── bot.py                      # Main bot class
│   │
│   ├── trading/                    # Trading modules
│   │   ├── __init__.py
│   │   ├── arbitrage_calculator.py # Arbitrage calculation
│   │   ├── trade_executor.py       # Trade execution
│   │   ├── state_manager.py        # State management
│   │   └── trade_logger.py         # Trade logging
│   │
│   ├── market/                     # Market modules
│   │   ├── __init__.py
│   │   └── market_discovery.py     # Market discovery
│   │
│   └── data/                       # Data modules
│       ├── __init__.py
│       └── price_fetcher.py        # Price fetching
├── utils/                     # Utilities
│   ├── __init__.py
│   └── __init__.py
├── config/                    # Configuration
│   ├── __init__.py
│   └── config_new_bot.py      # Strategy parameters
├── strategy.txt               # Mathematical strategy description
├── README.md                  # This documentation
└── run.py                     # Entry point
```

## Strategy Description

This bot implements a mathematical arbitrage strategy for 15-minute Polymarket markets. Based on the principle that when the sum of probabilities up + down < 1, guaranteed profit can be made.

## Mathematical Foundation

### Strategy Formula
```
bet_down / down = bet_up / up
total_bet = bet_down + bet_up
down + up < 1
```

### Coefficient k Calculation
```
k = total_bet / (up + down)
bet_up = k × up
bet_down = k × down
```

### Example
- up = 0.74, down = 0.25
- up + down = 0.99 < 1 ✅ (arbitrage condition met)
- total_bet = 20 USDC (10% of 200 USDC deposit)
- k = 20 / 0.99 = 20.2
- bet_up = 20.2 × 0.74 = 14.95 USDC
- bet_down = 20.2 × 0.25 = 5.05 USDC

### Guaranteed Profit
**Scenario 1: up = 0.99, down = 0.01**
- Profit_up = 14.95 × ((0.99/0.74) - 1) = 5.05 USDC
- Profit_down = 5.05 × ((0.01/0.25) - 1) = -4.85 USDC
- **Total profit: 0.20 USDC (1%)**

**Scenario 2: up = 0.51, down = 0.49**
- Profit_up = 14.95 × ((0.51/0.74) - 1) = -4.65 USDC
- Profit_down = 5.05 × ((0.49/0.25) - 1) = 4.85 USDC
- **Total profit: 0.20 USDC (1%)**

## Key Features

### ✅ Advantages
- **Guaranteed profit** when condition up + down < 1 is met
- **Mathematically sound** strategy
- **Low risk** - profit does not depend on event outcome
- **Automatic calculation** of optimal bet sizes

### ⚠️ Operating Conditions
- up + down < 1 (arbitrage opportunity)
- Minimum arbitrage difference (configured at 1%)
- Market liquidity for trade execution

## Bot Architecture

### Core Components

1. **BalancedArbitrageBot** - main bot class
2. **initialize_client()** - connection to Polymarket API
3. **discover_market()** - finding 15-minute markets
4. **get_current_prices()** - fetching current prices
5. **calculate_arbitrage_opportunity()** - arbitrage calculation
6. **execute_balanced_trade()** - trade execution
7. **monitor_market()** - monitoring for 15 minutes

### Integration with Main Bot

The bot uses proven components from the root file:
- **Connection** - `ClobClient` from `py_clob_client`
- **Market discovery** - Gamma API (`GAMMA_EVENTS_URL`)
- **Data models** - `MarketInfo`, `OrderBook`, `OrderBookEntry`
- **Configuration** - parameters from `config.py`

## Configuration Parameters

### Strategic Parameters
```python
balance_percent_per_trade = 0.10  # 10% of deposit per trade
min_arbitrage_threshold = 0.01    # Minimum arbitrage 1%
deposit_balance = 200.0           # Deposit size
```

### Technical Parameters
```python
DRY_RUN = True                    # Test mode
ORDER_TIMEOUT_SECONDS = 60       # Order timeout
LOG_LEVEL = "INFO"               # Logging level
```

## Running the Bot

### Test Mode
```bash
cd new_bot
python run.py
```

### Live Mode
1. Set `DRY_RUN = False` in root `config.py`
2. Ensure sufficient balance
3. Run: `python run.py`

## Components

### core/bot.py
Main class `BalancedArbitrageBot` with logic:
- Finding 15-minute markets
- Calculating arbitrage opportunities
- Executing balanced trades
- Monitoring positions
- Setting up main `logger` via `logging.basicConfig` and `logging.getLogger("BalancedArbitrageBot")`

### core/trading/state_manager.py
State management:
- Tracking positions (UP/DOWN contracts)
- Balance management
- Entry history
- P&L calculation

### core/trading/trade_logger.py
Logging:
- Recording all position entries
- Saving market sessions
- Daily statistics
- JSON files in `logs/`

## Monitoring

### What the bot shows:
- Current UP/DOWN prices
- Sum of probabilities
- Arbitrage difference
- Calculated bets
- Expected profit

### Results:
- Number of opportunities found
- Size of executed trades
- Profit obtained

## Security

### Risks
- **Liquidity** - market may not have sufficient liquidity
- **Volatility** - prices can change quickly
- **Execution** - possible delays in trade execution

### Protection
- Test mode by default
- Minimum arbitrage threshold
- Trade timeouts
- Logging of all operations

## Files

- `balanced_arbitrage_bot.py` - main bot code
- `strategy.txt` - mathematical strategy description
- `README.md` - this documentation

## Support

The bot is developed based on proven architecture of the main trading bot with adaptation for balanced arbitrage strategy.
