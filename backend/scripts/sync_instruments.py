"""Manual instrument sync — run on VPS after deploy or for testing."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.broker.instruments_sync import run_instrument_sync_job


async def main() -> None:
    await run_instrument_sync_job()
    print("Instrument sync finished")


if __name__ == "__main__":
    asyncio.run(main())
