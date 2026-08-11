# Migrating staging data into the `ist-prod` Atlas cluster

This runbook covers copying `contentlab-search`'s data from the staging
database into a new database in the `ist-prod` Atlas cluster, and
repointing the deployed `contentlab-search` service at it.

**Nothing in this document has been executed.** It is a set of instructions
and copy/paste commands with placeholder connection strings, written for
whoever runs the actual migration.

---

## Prerequisites - what you must supply before starting

Have these on hand before running anything below:

- [ ] **Staging MongoDB URI** with read access to the source database (a
      `mongodb+srv://...` connection string, e.g. from the `MONGODB_URI`
      value backing the `contentlab-search` k8s secret in staging).
- [ ] **Staging database name** (the `DATABASE_NAME` value for staging).
- [ ] **`ist-prod` cluster URI** with read/write access, and the name you
      want to give the new database in that cluster.
- [ ] **An Atlas user/role with permission to create Search/Vector Search
      indexes** on the `ist-prod` cluster (index creation is a separate
      permission from plain read/write in some Atlas setups).
- [ ] **A Grove API key and a Voyage API key** valid in whichever
      environment will run `scripts/reembed.py` against `ist-prod` (the
      re-embed step makes live calls to both).
- [ ] **`mongodump`/`mongorestore` (MongoDB Database Tools)** installed
      locally or wherever this runbook is executed, matching the Atlas
      server version (check `mongodump --version` compatibility).
- [ ] **`helm` and kubectl access** to the cluster/namespace running
      `contentlab-search`, with permission to run `helm ksec set` (or
      whatever secret-management flow your Kanopy/Drone setup uses - see
      `environments/{staging,prod}.yaml` and `.drone.yml` for the existing
      `contentlab-search` k8s secret name and Helm chart).
- [ ] **A maintenance/communication plan**: while `ist-prod` is being
      populated and re-embedded, semantic search results served from it
      will be incomplete or absent. Decide whether to cut traffic over
      before or after re-embedding completes.

---

## Collections to migrate

Verified against `backend/db/collections/*.json` (the seed fixtures) and
the collection names actually used in code (`db.get_collection(...)` calls
in `backend/routers/*.py`, and the `NEWS_COLLECTION`/`REDDIT_COLLECTION`
env vars used elsewhere):

| Collection      | Source of truth                                                          | Notes |
|-----------------|---------------------------------------------------------------------------|-------|
| `news`          | `backend/db/collections/news.json`, `NEWS_COLLECTION` env var             | Has `embedding` + `embedding_string` fields - vectors are stale Cohere vectors, see below. |
| `reddit_posts`  | `backend/db/collections/reddit_posts.json`, `REDDIT_COLLECTION` env var   | Same as `news`. |
| `suggestions`   | `backend/db/collections/suggestions.json`, `SUGGESTION_COLLECTION` env var| No embeddings stored; generated on demand. |
| `userProfiles`  | `backend/db/collections/userProfiles.json`, hardcoded in `routers/content.py` | |
| `drafts`        | `backend/db/collections/drafts.json`, hardcoded in `routers/drafts.py`    | |
| `preview`       | `backend/db/collections/preview.json`, hardcoded in `routers/drafts.py`  | Published, HTML-stripped drafts; feeds IST Media. |

There is no collection to exclude - migrate all six.

---

## Step 1 - dump staging

```bash
mongodump \
  --uri="mongodb+srv://<staging-user>:<staging-password>@<staging-cluster-host>/<staging-db-name>" \
  --db="<staging-db-name>" \
  --collection="news" \
  --collection="reddit_posts" \
  --collection="suggestions" \
  --collection="userProfiles" \
  --collection="drafts" \
  --collection="preview" \
  --out="./contentlab-staging-dump"
```

Notes:

- `mongodump` only accepts one `--collection` per invocation in some
  versions; if yours rejects repeated `--collection` flags, drop `--db`
  and `--collection` entirely and just point `--out` at a directory - that
  dumps every collection in the database, which is also fine here since we
  are migrating all six anyway:

  ```bash
  mongodump --uri="mongodb+srv://<staging-user>:<staging-password>@<staging-cluster-host>/<staging-db-name>" \
    --out="./contentlab-staging-dump"
  ```

- `mongodump` captures documents and regular (non-Search) indexes. It does
  **not** capture Atlas Search or Atlas Vector Search index definitions -
  see Step 3.

## Step 2 - restore into `ist-prod`

```bash
mongorestore \
  --uri="mongodb+srv://<ist-prod-user>:<ist-prod-password>@<ist-prod-cluster-host>/<ist-prod-db-name>" \
  --nsFrom="<staging-db-name>.*" \
  --nsTo="<ist-prod-db-name>.*" \
  --drop \
  "./contentlab-staging-dump/<staging-db-name>"
```

Notes:

- `--nsFrom`/`--nsTo` remap the database name from staging's to the new
  `ist-prod` database name, in case they differ (they likely will).
- `--drop` drops each target collection before restoring into it - safe on
  a brand-new database, but **omit it** if `ist-prod` already has data you
  don't want to lose.
- Run without `--drop` first and inspect counts if you're at all unsure;
  `mongorestore` is not itself dangerous, but a wrong `--nsTo` combined with
  `--drop` against the wrong database is exactly the kind of mistake this
  note exists to prevent.

## Step 3 - recreate Atlas Search / Vector Search indexes

`mongorestore` does not carry Atlas Search or Vector Search index
definitions - they must be recreated manually on `ist-prod` after the
restore. Use the existing index creator rather than the Atlas UI, so the
definition matches exactly what the code expects:

```bash
cd backend
MONGODB_URI="mongodb+srv://<ist-prod-user>:<ist-prod-password>@<ist-prod-cluster-host>" \
DATABASE_NAME="<ist-prod-db-name>" \
python _vector_search_idx_creator.py
```

This creates the `semantic_search_embeddings` vector index (1024
dimensions, cosine similarity) on both `news` and `reddit_posts`, matching
the index the application queries at runtime (see
`backend/embeddings/test_embeddings.py`'s `search_similar_content`, which
hits index name `semantic_search_embeddings` on field `embedding`).

If `_vector_search_idx_creator.py` reports the index already exists
(error code 68 / "IndexAlreadyExists"), that's a no-op warning, not a
failure - safe to ignore.

`backend/scripts/reembed.py` (added in this PR) also calls this same
index-creation logic automatically after re-embedding, via
`VectorSearchIDXCreator`, so **you can skip this step if you're about to
run Step 4 anyway.**

## Step 4 - re-embed: the restored vectors are stale Cohere vectors

Every `embedding` field restored from staging (and, separately, any
`embedding` baked into the `backend/db/collections/news.json` /
`reddit_posts.json` seed fixtures if you loaded those instead of or in
addition to the staging dump) was generated by the old Bedrock/Cohere
pipeline. Voyage and Cohere embeddings live in different, non-comparable
vector spaces - **`$vectorSearch` queries against un-re-embedded documents
will return meaningless results**, not just slightly-off ones.

Run the re-embedding script (added in this PR at
`backend/scripts/reembed.py`) against `ist-prod` before relying on search:

```bash
cd backend
MONGODB_URI="mongodb+srv://<ist-prod-user>:<ist-prod-password>@<ist-prod-cluster-host>" \
DATABASE_NAME="<ist-prod-db-name>" \
GROVE_API_KEY="<grove-api-key>" \
VOYAGE_API_KEY="<voyage-api-key>" \
python scripts/reembed.py --dry-run   # sanity check counts first

# then, once the dry run looks right:
MONGODB_URI="..." DATABASE_NAME="..." VOYAGE_API_KEY="..." \
  python scripts/reembed.py
```

The script re-embeds `news` and `reddit_posts` from their existing
`embedding_string` field (so it works whether that document came from the
staging dump or from loading the seed fixtures directly), is
batched/resumable, and ensures the vector search index exists on both
collections afterward - so if you already ran Step 3 manually, running
this script again is harmless (it treats "index already exists" as a
no-op).

## Step 5 - repoint the deployed service at `ist-prod`

Update the `contentlab-search` k8s secret (see `environments/prod.yaml`'s
`envSecrets.MONGODB_URI`/`DATABASE_NAME`, both currently pointing at the
`contentlab-search` secret) to the new connection details:

```bash
helm ksec set contentlab-search \
  MONGODB_URI="mongodb+srv://<ist-prod-user>:<ist-prod-password>@<ist-prod-cluster-host>" \
  DATABASE_NAME="<ist-prod-db-name>"
```

Then redeploy (or let the next Drone deploy pick up the secret change -
confirm your cluster's secret-refresh behavior; some setups require a pod
restart to pick up a changed secret even if the secret value itself
updates immediately).

## Verification checklist

- [ ] `mongorestore` completed with no fatal errors; document counts in
      `ist-prod` for each of the 6 collections roughly match staging
      (`db.<collection>.countDocuments({})` on both sides).
- [ ] `semantic_search_embeddings` vector index exists on both `news` and
      `reddit_posts` in `ist-prod` (Atlas UI -> Database -> Search, or
      `db.news.getSearchIndexes()` / `db.reddit_posts.getSearchIndexes()`).
- [ ] `scripts/reembed.py` ran to completion with `failed: 0` (or an
      acceptably small, understood number) for both collections.
- [ ] A manual `$vectorSearch` query (or hitting
      `POST /api/services/analyze` on the running service) against
      `ist-prod` returns sensible, on-topic results - not just "no error".
- [ ] The `contentlab-search` service's `/health` endpoint is green after
      the secret update and redeploy.
- [ ] Unique indexes exist on `ist-prod` (run
      `MongoDBConnector().create_unique_indexes()` / `ensure_indexes()`, or
      let the scheduler's startup path do it - see
      `backend/scheduler_job/data_scheduler.py`'s `__main__` block) so
      duplicate-detection behaves the same as staging.
- [ ] Old staging `MONGODB_URI`/`DATABASE_NAME` values are not left
      reachable from anywhere they shouldn't be (rotate staging creds if
      this migration is part of a decommission, not just a copy).
