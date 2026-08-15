# Databricks notebook source
# MAGIC %md
# MAGIC # Weather Embedding Pipeline
# MAGIC Reads unembedded rows from `weather_documents`, chunks + embeds their
# MAGIC narrative text, and writes vectors into `weather_embeddings`.

# COMMAND ----------

# DBTITLE 1,Imports
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer

import lakebase

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

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
def fetch_unembedded_documents():
    return lakebase.run_query(
        """
        SELECT d.id, d.narrative_text
        FROM weather_documents d
        LEFT JOIN weather_embeddings e ON e.document_id = d.id
        WHERE e.document_id IS NULL
        """
    )


docs = fetch_unembedded_documents()
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
model = SentenceTransformer(EMBEDDING_MODEL_NAME)
texts = [chunk for (_, _, chunk) in pending]
vectors = model.encode(texts, show_progress_bar=True)

print(f"Encoded {len(vectors)} chunks.")

# COMMAND ----------

# DBTITLE 1,Write embeddings to Lakebase
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

with lakebase.get_connection() as conn:
    with conn.cursor() as cur:
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
