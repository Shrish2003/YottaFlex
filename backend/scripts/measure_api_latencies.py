"""Measure query performance and API latencies on the full 2,028,036-reading database."""

from __future__ import annotations

import statistics
import time
from fastapi.testclient import TestClient

from backend.app.main import app


def measure_endpoint(client: TestClient, path: str, iterations: int = 10) -> dict[str, float]:
    # Warmup
    r = client.get(path)
    if r.status_code != 200:
        return {"status": r.status_code, "error": r.text}

    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        resp = client.get(path)
        t_el = (time.perf_counter() - t0) * 1000  # ms
        if resp.status_code == 200:
            latencies.append(t_el)

    return {
        "status": 200,
        "iterations": iterations,
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "median_ms": round(statistics.median(latencies), 2),
    }


def main():
    print("=" * 60)
    print("API QUERY LATENCY BENCHMARK (ON 2,028,036 SENSOR READINGS)")
    print("=" * 60)

    client = TestClient(app)

    endpoints = [
        ("List Shipments (limit=10)", "/api/shipments?limit=10"),
        ("Get Shipment SHP-2026-000001", "/api/shipments/SHP-2026-000001"),
        ("Get Shipment Summary SHP-2026-000001", "/api/shipments/SHP-2026-000001/summary"),
        ("Get Excursion EXC-2026-000001", "/api/excursions/EXC-2026-000001"),
        ("Quality Summary (/api/quality/summary)", "/api/quality/summary"),
        ("Metrics Summary (/api/metrics/summary)", "/api/metrics/summary"),
    ]

    results = {}
    for label, path in endpoints:
        print(f"Benchmarking: {label} ({path})...")
        res = measure_endpoint(client, path)
        results[label] = res
        if res.get("status") == 200:
            print(f"  -> Median: {res['median_ms']:>6.2f} ms | Mean: {res['mean_ms']:>6.2f} ms | Min: {res['min_ms']:>6.2f} ms | Max: {res['max_ms']:>6.2f} ms")
        else:
            print(f"  -> Error: status {res.get('status')}: {res.get('error')}")

    import json
    with open("verification/api_query_benchmarks.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved benchmarks to verification/api_query_benchmarks.json")


if __name__ == "__main__":
    main()
