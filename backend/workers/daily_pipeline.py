"""Worker: daily pipeline orchestrator."""
import logging
from datetime import datetime

from backend.workers.match_importer import import_new_matches, refresh_views

logger = logging.getLogger(__name__)


def run_daily():
    """Full daily pipeline: import matches, refresh views, log."""
    start = datetime.now()
    logger.info("Daily pipeline started at %s", start.isoformat())

    # Step 1: Import new matches
    stats = import_new_matches(days_back=3)
    logger.info("Import: %s", stats)

    # Step 2: Refresh materialized views
    refresh_views()

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("Daily pipeline completed in %.1fs", elapsed)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_daily()
