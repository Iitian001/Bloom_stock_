import uvicorn
from loguru import logger
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

if __name__ == "__main__":
    logger.info("Starting Bloom_Stock Live Shadow API on port 8000...")
    uvicorn.run("bloom_stock.services.api.main:app", host="0.0.0.0", port=8000, reload=True)
