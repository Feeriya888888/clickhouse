"""
Загрузка CSV-файлов из data/ в ClickHouse через HTTP-интерфейс.
Только стандартная библиотека Python 3.9+ (urllib).

Перед запуском: выполните sql/schema.sql в ClickHouse.

Запуск:
    python scripts/load_data.py --host http://localhost:8123 --user analyst --password analyst_pass
"""
import argparse
import os
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

TABLES = [
    ("shop.users", "users.csv"),
    ("shop.products", "products.csv"),
    ("shop.events", "events.csv"),
    ("shop.orders", "orders.csv"),
    ("shop.order_items", "order_items.csv"),
]


def load_table(host, auth, table, filename, skip_header=False):
    path = os.path.join(DATA_DIR, filename)
    size = os.path.getsize(path)
    print(f"[->] {table} из {filename} ({size / 1e6:.1f} МБ)...")
    with open(path, "rb") as f:
        if skip_header:
            f.readline()
        body = f.read()
    url = f"{host}/?query=" + urllib.request.quote(f"INSERT INTO {table} FORMAT CSV")
    req = urllib.request.Request(url, data=body, method="POST")
    import base64
    token = base64.b64encode(auth.encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req) as resp:
        resp.read()
    print(f"[ok] {table}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://localhost:8123")
    ap.add_argument("--user", default="analyst")
    ap.add_argument("--password", default="analyst_pass")
    args = ap.parse_args()
    auth = f"{args.user}:{args.password}"

    for table, filename in TABLES:
        # Наши CSV без заголовков (совпадают с порядком колонок в схеме)
        load_table(args.host, auth, table, filename, skip_header=False)

    print("Загрузка завершена. Проверьте: SELECT count() FROM shop.events;")


if __name__ == "__main__":
    main()
