--Create documents table

CREATE TABLE IF NOT EXISTS weather_documents (
    id TEXT PRIMARY KEY,
    location TEXT NOT NULL,
    source_type TEXT NOT NULL,
    headline TEXT,
    narrative_text TEXT NOT NULL,
    issued_at TIMESTAMPTZ,
    payload JSONB NOT NULL,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
;

-- Creating Indexes
CREATE INDEX IF NOT EXISTS idx_weather_documents_location 
    ON weather_documents (location)
;

--Verify table was created
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE 1=1
    AND table_name = 'weather_documents'
ORDER BY ordinal_position
;