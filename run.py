import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

from core.bot import BalancedArbitrageBot


async def main():
    private_key = os.getenv('PRIVATE_KEY')
    proxy = os.getenv('POLYMARKET_PROXY')
    
    if not private_key or not proxy:
        print("ERROR: Keys not found in .env file")
        print("Create a .env file based on .env.example")
        return
    
    os.environ['PRIVATE_KEY'] = private_key
    os.environ['POLYMARKET_PROXY'] = proxy
    
    print("=" * 80)
    print("STARTING ARBITRAGE BOT")
    print("=" * 80)
    
    bot = BalancedArbitrageBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
    except Exception as e:
        print(f"\n\nError starting bot: {e}")
        import traceback
        traceback.print_exc()
