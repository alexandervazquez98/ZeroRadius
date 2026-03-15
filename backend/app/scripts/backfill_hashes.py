"""
T32 — Hash backfill script for radpostauth records.

Reads all existing radpostauth rows with integrity_hash IS NULL
and computes + stores a SHA-256 hash for each one using IntegrityHashService.

Usage:
    cd backend
    python -m app.scripts.backfill_hashes

After running:
    SELECT COUNT(*) FROM radpostauth WHERE integrity_hash IS NULL;
    -- should return 0
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("backfill_hashes")


async def run_backfill() -> None:
    """Entry point: open a DB session and run the hash backfill."""
    from app.db.session import SessionLocal  # type: ignore[attr-defined]
    from app.services.integrity import backfill_hashes

    logger.info("Starting integrity hash backfill for radpostauth records...")

    async with SessionLocal() as db:  # type: ignore[attr-defined]
        total = await backfill_hashes(db, batch_size=500)

    if total == 0:
        logger.info("No records needed backfilling (all hashes already present).")
    else:
        logger.info("Backfill complete. Total records updated: %d", total)


def main() -> None:
    asyncio.run(run_backfill())


if __name__ == "__main__":
    main()
