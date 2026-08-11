#!/usr/bin/env python3
# ---- reembed.py ----

"""
Re-embed stale Cohere vectors with Voyage.

Voyage and the old Bedrock Cohere model are not comparable embedding
spaces, so every `embedding` field written before this migration is now
semantically stale (and any freshly loaded seed fixture under
backend/db/collections/*.json still carries baked-in Cohere vectors too).
This script re-embeds each document's existing `embedding_string` field
with Voyage and overwrites `embedding` in place.

Usage:
    python backend/scripts/reembed.py
    python backend/scripts/reembed.py --dry-run
    python backend/scripts/reembed.py --collection news --batch-size 50
    python backend/scripts/reembed.py --force   # re-embed even already-migrated docs

Run this:
  - once, against staging/prod, to fix documents left over from the
    Bedrock/Cohere pipeline
  - after loading the backend/db/collections/*.json seed fixtures into a
    fresh database (they contain baked-in Cohere vectors that must not be
    used as-is)

This script does NOT touch backend/db/collections/*.json - those seed
fixtures are left as historical examples; their baked-in vectors are stale
Cohere ones, so re-run this script after loading them.
"""

import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, Iterable, List

# sys.path hack to reach the backend/ package modules, matching the
# convention already used by embeddings/process_embeddings.py etc.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mdb import MongoDBConnector  # noqa: E402
from grove.embeddings_client import VoyageEmbeddings  # noqa: E402
from _vector_search_idx_creator import VectorSearchIDXCreator  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Collection names (same env vars/defaults used elsewhere in the codebase)
NEWS_COLLECTION = os.getenv("NEWS_COLLECTION", "news")
REDDIT_COLLECTION = os.getenv("REDDIT_COLLECTION", "reddit_posts")

# Vector index config, kept in sync with embeddings/process_embeddings.py
VECTOR_INDEX_NAME = "semantic_search_embeddings"
VECTOR_FIELD = "embedding"
VECTOR_DIMENSIONS = 1024
VECTOR_SIMILARITY = "cosine"

DEFAULT_BATCH_SIZE = 25
BATCH_SLEEP_SECONDS = 0.5  # be gentle on the Voyage endpoint / avoid rate limits

# Field stamped onto each document after a successful re-embed, so re-runs
# are resumable/idempotent: by default we only process documents that are
# missing this field or stamped with a different model id.
EMBEDDING_MODEL_FIELD = "embedding_model"


def _iter_batches(items: List[Dict[str, Any]], batch_size: int) -> Iterable[List[Dict[str, Any]]]:
    """Yield successive batch_size-sized chunks from items."""
    for start in range(0, len(items), batch_size):
        yield items[start:start + batch_size]


def reembed_collection(
    db_connector: MongoDBConnector,
    embedder: VoyageEmbeddings,
    collection_name: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, int]:
    """
    Re-embed every document in `collection_name` that has an
    `embedding_string` field, using Voyage, and overwrite `embedding`.

    Resumable/idempotent: unless `force` is set, documents already stamped
    with the current Voyage model id (via EMBEDDING_MODEL_FIELD) are
    skipped. Re-running the script after an interruption, or after loading
    additional seed data, only processes what's left to do.

    Args:
        db_connector: MongoDBConnector, the database connector
        embedder: VoyageEmbeddings, the embeddings client to use
        collection_name: str, the collection to process
        batch_size: int, number of documents to embed per batch
        dry_run: bool, if True, log what would happen without calling
            Voyage or writing to MongoDB
        force: bool, if True, re-embed even documents already stamped with
            the current model

    Returns:
        Dict[str, int]: counts of processed/failed/total documents considered
    """
    collection = db_connector.get_collection(collection_name)

    query: Dict[str, Any] = {"embedding_string": {"$exists": True, "$ne": None}}
    if not force:
        query[EMBEDDING_MODEL_FIELD] = {"$ne": embedder.model_id}

    documents = list(collection.find(query, {"_id": 1, "embedding_string": 1}))
    total = len(documents)
    logger.info(f"[{collection_name}] Found {total} documents to re-embed (force={force})")

    processed, failed = 0, 0

    for batch_num, batch in enumerate(_iter_batches(documents, batch_size), start=1):
        for doc in batch:
            doc_id = doc["_id"]
            text = doc.get("embedding_string")
            if not text:
                continue
            try:
                if dry_run:
                    logger.info(f"[{collection_name}] DRY RUN would re-embed _id={doc_id}")
                    processed += 1
                    continue

                embedding = embedder.predict(text, input_type="document")
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {
                        VECTOR_FIELD: embedding,
                        EMBEDDING_MODEL_FIELD: embedder.model_id,
                    }},
                )
                processed += 1
            except Exception as e:
                failed += 1
                logger.error(f"[{collection_name}] Failed to re-embed _id={doc_id}: {e}")

        logger.info(
            f"[{collection_name}] Batch {batch_num}: processed {processed}/{total} so far "
            f"({failed} failed)"
        )
        if not dry_run and batch_num * batch_size < total:
            time.sleep(BATCH_SLEEP_SECONDS)

    logger.info(f"[{collection_name}] Finished: processed={processed} failed={failed} total={total}")
    return {"processed": processed, "failed": failed, "total": total}


def ensure_vector_search_indexes(collections: List[str]) -> None:
    """
    Ensure the `semantic_search_embeddings` vector index exists on each
    collection in `collections`. Reuses VectorSearchIDXCreator
    (backend/_vector_search_idx_creator.py) rather than duplicating its
    index-creation logic; it is safe to call even if the index already
    exists (create_search_index treats "already exists" as a no-op warning,
    not an error).

    Args:
        collections: List[str], the collection names to ensure the index on
    Returns:
        None
    """
    for collection_name in collections:
        try:
            vs_creator = VectorSearchIDXCreator(collection_name=collection_name)
            result = vs_creator.create_index(
                index_name=VECTOR_INDEX_NAME,
                vector_field=VECTOR_FIELD,
                dimensions=VECTOR_DIMENSIONS,
                similarity_metric=VECTOR_SIMILARITY,
            )
            logger.info(f"[{collection_name}] Vector search index: {result}")
        except Exception as e:
            logger.error(f"[{collection_name}] Error ensuring vector search index: {e}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the re-embedding script."""
    parser = argparse.ArgumentParser(
        description=(
            "Re-embed news/reddit_posts documents with Voyage, replacing stale "
            "Cohere vectors left over from the Bedrock pipeline (or baked into "
            "seed fixtures)."
        )
    )
    parser.add_argument(
        "--collection",
        action="append",
        dest="collections",
        choices=[NEWS_COLLECTION, REDDIT_COLLECTION],
        help=(
            f"Collection to re-embed. Repeatable. Defaults to both "
            f"'{NEWS_COLLECTION}' and '{REDDIT_COLLECTION}'."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of documents to process per batch (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be re-embedded without calling Voyage or writing to MongoDB.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Re-embed documents even if they're already stamped with the current "
            "Voyage model (by default, re-running the script skips those, making "
            "it resumable/idempotent)."
        ),
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip the ensure-vector-search-index step at the end.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point: re-embed the requested collections, then ensure vector indexes."""
    args = parse_args()
    collections = args.collections or [NEWS_COLLECTION, REDDIT_COLLECTION]

    logger.info(
        f"Re-embedding collections: {collections} (dry_run={args.dry_run}, force={args.force})"
    )

    db_connector = MongoDBConnector()
    embedder = VoyageEmbeddings()

    summary: Dict[str, Dict[str, int]] = {}
    for collection_name in collections:
        summary[collection_name] = reembed_collection(
            db_connector,
            embedder,
            collection_name,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            force=args.force,
        )

    if args.dry_run:
        logger.info("Dry run: skipping vector search index check.")
    elif not args.skip_index:
        ensure_vector_search_indexes(collections)

    logger.info(f"Re-embedding complete: {summary}")


if __name__ == "__main__":
    main()
