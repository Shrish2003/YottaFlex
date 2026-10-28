import json
import time
import urllib.request

endpoints = [
    ("Shipments List", "http://127.0.0.1:8000/api/shipments?page=1&page_size=25"),
    ("Single Shipment", "http://127.0.0.1:8000/api/shipments/SHP-2026-000001"),
    ("Shipment Summary", "http://127.0.0.1:8000/api/shipments/SHP-2026-000001/summary"),
    ("Excursions List", "http://127.0.0.1:8000/api/excursions?page=1&page_size=25"),
    ("Single Excursion", "http://127.0.0.1:8000/api/excursions/EXC-2026-000001"),
]

for label, url in endpoints:
    t0 = time.perf_counter()
    try:
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read().decode("utf-8"))
        el = time.perf_counter() - t0
        print(f"[OK] {label:20s}: {req.status} in {el:.2f}s | keys: {list(data.keys())[:5]}")
    except Exception as e:
        print(f"[ERROR] {label:20s}: {e}")
