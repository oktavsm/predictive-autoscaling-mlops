from datetime import datetime, timedelta, timezone
import os
import pandas as pd
import requests

# Port forward Prometheus or run directly
PROM = os.getenv("PROM_URL", "http://127.0.0.1:9090")

end = datetime.now(timezone.utc)
start = end - timedelta(minutes=30)
step = 15

queries = {
    "request_rate": """
        sum(
          rate(
            caddy_http_requests_total{
              host=~"api.titipin.me.*"
            }[1m]
          )
        )
    """,
    "php_cpu_cores": """
        sum(
          rate(
            container_cpu_usage_seconds_total{
              namespace="titipin",
              pod=~"laravel-backend-.*",
              container="php"
            }[1m]
          )
        )
    """,
    "php_memory_bytes": """
        sum(
          container_memory_working_set_bytes{
            namespace="titipin",
            pod=~"laravel-backend-.*",
            container="php"
          }
        )
    """,
    "replicas": """
        kube_deployment_status_replicas{
          namespace="titipin",
          deployment="laravel-backend"
        }
    """,
    "p95_latency_seconds": """
        histogram_quantile(
          0.95,
          sum by (le) (
            rate(
              caddy_http_request_duration_seconds_bucket{
                host=~"api.titipin.me.*"
              }[1m]
            )
          )
        )
    """,
}


def query_range(promql):
    try:
        response = requests.get(
            f"{PROM}/api/v1/query_range",
            params={
                "query": promql,
                "start": start.timestamp(),
                "end": end.timestamp(),
                "step": step,
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()["data"]["result"]
        if not result:
            return pd.Series(dtype=float)

        values = result[0]["values"]
        return pd.Series(
            {
                pd.to_datetime(ts, unit="s", utc=True): float(value)
                for ts, value in values
            }
        )
    except Exception as e:
        print(f"Warning on query: {e}")
        return pd.Series(dtype=float)


frame = pd.DataFrame()

for name, query in queries.items():
    frame[name] = query_range(query)

frame.index.name = "timestamp"
frame = frame.sort_index()

output_file = os.path.join(os.path.dirname(__file__), "../src/data/demo_metrics.csv")
os.makedirs(os.path.dirname(output_file), exist_ok=True)
frame.to_csv(output_file)

print(frame.tail(20))
print(f"\nSaved successfully to: {output_file}")
