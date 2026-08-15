from fastapi import FastAPI
from pydantic import BaseModel, Field
import json
import lakebase
from weather_client import WeatherClient


app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


class LocationInput(BaseModel):
    lat: float
    lon: float
    label: str


class SyncRequest(BaseModel):
    locations: list[LocationInput]
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
                                synced_at = EXCLUDED.synced_at
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


@app.post("/weather/sync")
def sync_weather(body: SyncRequest):
    client = WeatherClient()
    total_synced = 0

    for location in body.locations:
        docs = client.fetch_documents(
            location.lat, location.lon, location.label, limit=body.limit
        )
        total_synced += _upsert_weather_batch(docs)

    return {"synced": total_synced, "locations": [loc.label for loc in body.locations]}
