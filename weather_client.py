import requests


class WeatherClient:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "Weather-homework f.marquezr96@gmail.com"}
        )

    def get(self, path, params=None):
        url = f"https://api.weather.gov{path}"
        resp = self._session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def resolve_point(self, lat, lon):
        data = self.get(f"/points/{lat},{lon}")
        return data["properties"]

    def get_active_alerts(self, lat, lon):
        data = self.get("/alerts/active", params={"point": f"{lat},{lon}"})
        return data.get("features", [])

    def get_forecast(self, forecast_url):
        data = self._session.get(forecast_url, timeout=15).json()
        return data["properties"]["periods"]

    # Normalization layer

    def _normalize_alert(self, feature, label):
        props = feature.get("properties", {})

        narrative = " ".join(
            filter(None, [props.get("description"), props.get("instruction")])
        ).strip()

        return {
            "id": props.get("id") or feature.get("id"),
            "location": label,
            "source_type": "alert",
            "headline": props.get("event", "Weather Alert"),
            "narrative_text": narrative,
            "issued_at": props.get("effective"),
            "payload": feature,
        }

    def _normalize_forecast_period(self, period, label):
        period_id = f"{label}:{period.get('number')}:{period.get('startTime')}"
        return {
            "id": period_id,
            "location": label,
            "source_type": "forecast",
            "headline": period.get("name", "Forecast"),
            "narrative_text": period.get("detailedForecast", ""),
            "issued_at": period.get("startTime"),
            "payload": period,
        }

    def fetch_documents(self, lat, lon, label, limit=50):
        point = self.resolve_point(lat, lon)
        docs = []

        for feature in self.get_active_alerts(lat, lon)[:limit]:
            docs.append(self._normalize_alert(feature, label))

        for period in self.get_forecast(point["forecast"])[:limit]:
            docs.append(self._normalize_forecast_period(period, label))

        return docs


# if __name__ == "__main__":
#     client = WeatherClient()
#     docs = client.fetch_documents(32.7767, -96.7970, "Dallas, TX")
#     print(f"{len(docs)} documents")
#     for d in docs[:3]:
#         print(d["source_type"], "-", d["headline"])
