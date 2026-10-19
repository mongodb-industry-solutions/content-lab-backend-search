# ---- test.py ----

# Read-only smoke test for the scheduler's data layer.
#
# This file previously called nothing: every job invocation was commented out, so it
# always reported "-0" deltas and "Test completed" regardless of the state of the
# system. It is now a real check.
#
# It performs NO writes: no scraping, no embedding, no cleanup. Run it to confirm the
# database is reachable, the collections exist, the indexes the code depends on are
# present, and the scheduler's timezone is what the API claims.
#
# Run:  python scheduler_job/test.py
# Exit: 0 if every hard check passed, 1 otherwise.

import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_scheduler import schedule  # noqa: E402
from db.mdb import MongoDBConnector  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SmokeTest")

# Collections the application reads and writes.
COLLECTIONS = ["news", "reddit_posts", "suggestions", "drafts", "userProfiles", "preview"]

# Indexes declared in MongoDBConnector.create_unique_indexes(). Reported rather than
# enforced: creating them on a collection that already holds duplicates fails, and
# doing so silently changes what documents are permitted.
DECLARED_UNIQUE_INDEXES = {
    "news": ["unique_news_url", "unique_news_title_source"],
    "reddit_posts": ["unique_reddit_id", "unique_reddit_url", "unique_reddit_title_subreddit"],
    "suggestions": ["unique_suggestion_topic_query_label", "unique_suggestion_url_query"],
}

# Env vars the service needs. Only presence is checked; values are never printed.
REQUIRED_ENV = [
    "MONGODB_URI",
    "DATABASE_NAME",
    "GROVE_API_KEY",
    "VOYAGE_API_KEY",
    "NEWSAPI_KEY",
    "REDDIT_CLIENT_ID",
    "REDDIT_SECRET",
    "TAVILY_API_KEYS",
]

VECTOR_INDEX_NAME = "semantic_search_embeddings"


def main() -> int:
    failures = []

    # ---- 1. Configuration ----
    logger.info("--- configuration ---")
    for name in REQUIRED_ENV:
        present = bool(os.getenv(name))
        logger.info(f"  {name:<20} {'set' if present else 'MISSING'}")
        if not present:
            failures.append(f"env var {name} is not set")

    # ---- 2. Connectivity + collection counts ----
    logger.info("--- database ---")
    try:
        db = MongoDBConnector()
        db.client.admin.command("ping")
    except Exception as e:
        logger.error(f"  cannot reach MongoDB: {e}")
        return 1

    logger.info(f"  database: {db.db.name}")
    for name in COLLECTIONS:
        count = db.get_collection(name).count_documents({})
        logger.info(f"  {name:<14} {count:>6} documents")

    # ---- 3. Indexes ----
    logger.info("--- indexes ---")
    for name in COLLECTIONS:
        present = set(db.get_collection(name).index_information().keys())
        logger.info(f"  {name:<14} {sorted(present)}")

    missing = []
    for name, indexes in DECLARED_UNIQUE_INDEXES.items():
        present = set(db.get_collection(name).index_information().keys())
        for index in indexes:
            if index not in present:
                missing.append(f"{name}.{index}")
    if missing:
        logger.warning(
            f"  declared-but-absent unique indexes ({len(missing)}): {', '.join(missing)}"
        )
        logger.warning(
            "  These are only created by MongoDBConnector.create_unique_indexes(), which "
            "the running app never calls. Deduplicate before creating them."
        )

    # ---- 4. Atlas vector search index ----
    logger.info("--- vector search ---")
    for name in ("news", "reddit_posts"):
        try:
            found = False
            for idx in db.get_collection(name).list_search_indexes():
                if idx.get("name") == VECTOR_INDEX_NAME:
                    found = True
                    status = idx.get("status")
                    logger.info(f"  {name:<14} {VECTOR_INDEX_NAME}: {status}")
                    if status != "READY":
                        failures.append(f"{name} vector index status is {status}, not READY")
            if not found:
                logger.error(f"  {name:<14} {VECTOR_INDEX_NAME}: MISSING")
                failures.append(f"{name} is missing the {VECTOR_INDEX_NAME} vector index")
        except Exception as e:
            logger.error(f"  {name:<14} could not list search indexes: {e}")
            failures.append(f"cannot list search indexes for {name}: {e}")

    # ---- 5. Scheduler timezone ----
    logger.info("--- scheduler ---")
    tz = getattr(schedule, "_Scheduler__tzinfo", None)
    logger.info(f"  tzinfo           {tz if tz is not None else 'None (naive LOCAL time!)'}")
    logger.info(f"  registered jobs  {len(schedule.jobs)}")
    if tz is None:
        failures.append(
            "scheduler tzinfo is None - jobs fire on naive local time, not UTC"
        )

    # ---- Summary ----
    logger.info("--- summary ---")
    if failures:
        logger.error(f"{len(failures)} check(s) failed:")
        for f in failures:
            logger.error(f"  - {f}")
        return 1

    logger.info("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
