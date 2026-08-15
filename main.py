from fastapi import FastAPI
from pydantic import BaseModel, Field
import json
import lakebase


app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


class SyncRequest(BaseModel):
    locations: list[str]
    limit: int = Field(default=50, ge=1, le=200)


def _upsert_weather_batch(docs):
    count = 0
    with lakebase.get_connection() as conn:
        with conn.cursor() as cur:
            for doc in docs:
                cur.execute(
                    """
                    INSERT INTO weather_documents (
                        id,
                        location,
                        source_type,
                        headline,
                        narrative_text,
                        issued_at,
                        payload,
                        synced_at
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (id) DO UPDATE
                            SET narrative_text = EXCLUDED.narrative_text,
                                headline = EXCLUDED.headline,
                                issued_at = EXCLUDED.issued_at,
                                payload = EXCLUDED.payload,
                                synced_at = EXCLUDED.synced_at,
                    """,
                    (
                        doc["id"],
                        doc["location"],
                        doc["source_type"],
                        doc.get("headline"),
                        doc["narrative_text"],
                        doc.get("issued_at"),
                        json.dumps(doc["payload"]),
                    ),
                )
                count += 1
            conn.commit()
    return count
