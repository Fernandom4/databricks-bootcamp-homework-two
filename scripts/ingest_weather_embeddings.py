# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Weather Embedding Pipeline
# MAGIC Reads unembedded rows from `weather_documents`, chunks + embeds their
# MAGIC narrative text, and writes vectors into `weather_embeddings`.

# COMMAND ----------

# DBTITLE 1,Install required packages
# MAGIC %pip uninstall -y psycopg2 psycopg2-binary
# MAGIC %pip install -q 'databricks-sdk>=0.118.0' sentence-transformers trafilatura requests pandas
# MAGIC

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Config
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
LAKEBASE_SECRET_SCOPE = "Homework_two"
LAKEBASE_SECRET_KEY = "lakebase-url"

# COMMAND ----------

# DBTITLE 1,Resolve Lakebase connection
import base64

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()


def get_lakebase_url():
    secret = w.secrets.get_secret(scope=LAKEBASE_SECRET_SCOPE, key=LAKEBASE_SECRET_KEY)
    return base64.b64decode(secret.value).decode("utf-8")


lakebase_url = get_lakebase_url()
print("Resolved Lakebase connection URL.")

# COMMAND ----------

# DBTITLE 1,Chunking function

def chunk_text(text, chunk_size, chunk_overlap):
    """Sliding-window character chunking."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    step = max(chunk_size - chunk_overlap, 1)

    for start in range(0, len(text), step):
        piece = text[start : start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(text):
            break

    return chunks


# COMMAND ----------

# DBTITLE 1,Find unembedded documents
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(lakebase_url, cursor_factory=RealDictCursor)
cur = conn.cursor()

cur.execute(
    """
    SELECT d.id, d.narrative_text
    FROM weather_documents d
    LEFT JOIN weather_embeddings e ON e.document_id = d.id
    WHERE e.document_id IS NULL
    """
)
docs = cur.fetchall()
print(f"{len(docs)} unembedded documents found.")

# COMMAND ----------

# DBTITLE 1,Chunk all documents
pending = []
for doc in docs:
    chunks = chunk_text(doc["narrative_text"], CHUNK_SIZE, CHUNK_OVERLAP)
    for i, chunk in enumerate(chunks):
        pending.append((doc["id"], i, chunk))

print(f"{len(pending)} chunks to embed.")

# COMMAND ----------

# DBTITLE 1,Load model and embed
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    EMBEDDING_MODEL_NAME, cache_folder="/tmp/.cache/huggingface"
)
texts = [chunk for (_, _, chunk) in pending]
vectors = model.encode(texts, show_progress_bar=True)

print(f"Encoded {len(vectors)} chunks.")

# COMMAND ----------

# DBTITLE 1,Write embeddings to Lakebase
from psycopg2.extras import execute_values

rows = [
    (
        f"{doc_id}:{chunk_index}",
        doc_id,
        chunk_index,
        chunk,
        vector.tolist(),
        EMBEDDING_MODEL_NAME,
    )
    for (doc_id, chunk_index, chunk), vector in zip(pending, vectors)
]

execute_values(
    cur,
    """
    INSERT INTO weather_embeddings (
        id,
        document_id,
        chunk_index,
        chunk_text,
        embedding,
        model_name
    )
    VALUES %s
    ON CONFLICT (id) DO NOTHING
    """,
    rows,
    template="(%s, %s, %s, %s, %s::vector, %s)",
)
conn.commit()

print(f"Done. {len(rows)} chunk embeddings written.")

cur.close()
conn.close()