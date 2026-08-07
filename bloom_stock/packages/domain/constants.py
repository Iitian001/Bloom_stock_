from datetime import time
from zoneinfo import ZoneInfo

NSE_TIMEZONE = ZoneInfo('Asia/Kolkata')
DEFAULT_MARKET_OPEN = time(9, 15)
DEFAULT_MARKET_CLOSE = time(15, 30)
DEFAULT_NO_NEW_ENTRIES = time(14, 30)
DEFAULT_LIQUIDATION_START = time(14, 55)
DEFAULT_HARD_FLAT = time(15, 10)
INSTRUMENT_MASTER_URL = 'https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json'
