"""
Генератор синтетических данных для аналитики интернет-магазина.
Создаёт CSV-файлы в каталоге data/: users.csv, products.csv,
events.csv, orders.csv, order_items.csv

Запуск: python scripts/generate_data.py [--users 20000] [--events 2000000]
Зависимости: только стандартная библиотека Python 3.9+
"""
import argparse
import csv
import datetime as dt
import os
import random

random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CITIES = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург", "Сочи"]
SOURCES = ["organic", "ads", "email", "social", "referral"]
DEVICES = ["desktop", "mobile", "tablet"]
CATEGORIES = {
    "Электроника": (2000, 60000),
    "Одежда": (500, 15000),
    "Дом и кухня": (300, 12000),
    "Спорт": (400, 25000),
    "Книги": (200, 3000),
}
EVENT_TYPES = ["page_view", "product_view", "add_to_cart", "checkout", "purchase"]

N_USERS = 20000
N_EVENTS = 2_000_000
START = dt.datetime(2024, 1, 1)
DAYS = 540  # ~18 месяцев истории


def wchoice(seq, weights):
    total = sum(weights)
    r = random.uniform(0, total)
    acc = 0.0
    for s, w in zip(seq, weights):
        acc += w
        if r <= acc:
            return s
    return seq[-1]


def make_products():
    products = []
    pid = 1
    for cat, (lo, hi) in CATEGORIES.items():
        for i in range(40):
            products.append({
                "product_id": pid,
                "name": f"{cat} #{pid:04d}",
                "category": cat,
                "price": random.randrange(lo, hi, 50),
            })
            pid += 1
    return products


def user_pool(n):
    """Часть пользователей активна чаще — чтобы retention был реалистичным."""
    pool = []
    for uid in range(1, n + 1):
        # 20% активных (частые сессии), 50% средние, 30% спящие
        tier = "hot" if uid % 10 in (1, 2) else ("warm" if uid % 4 == 0 else "cold")
        pool.append(tier)
    return pool


def write_users(path, n):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for uid in range(1, n + 1):
            signup = START + dt.timedelta(days=random.randint(0, DAYS - 60))
            w.writerow([uid, random.choice(CITIES),
                        signup.strftime("%Y-%m-%d"), random.choice(SOURCES)])


def write_products(path, products):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for p in products:
            w.writerow([p["product_id"], p["name"], p["category"], p["price"]])


def write_events(path, n, users_tiers, products):
    session_id = 1
    eid = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        while eid < n:
            tier = wchoice(["hot", "warm", "cold"], [0.35, 0.4, 0.25])
            uid = random.randint(1, len(users_tiers))
            if users_tiers[uid - 1] != tier:
                continue
            if tier == "hot":
                days_ahead = random.randint(0, DAYS - 1)
            elif tier == "warm":
                days_ahead = random.randint(0, DAYS - 30)
            else:
                days_ahead = random.randint(0, DAYS - 300)
            hour = random.randint(8, 23)
            t = START + dt.timedelta(days=days_ahead, hours=hour,
                                     minutes=random.randint(0, 59),
                                     seconds=random.randint(0, 59))
            device = wchoice(DEVICES, [0.4, 0.5, 0.1])
            # Внутри сессии пользователь двигается по воронке
            steps = [i / 100 for i in [50, 80, 40, 20, 12]]  # вероятности перехода
            # page_view -> product_view -> add_to_cart -> checkout -> purchase
            p_prev = 1.0
            for step, event in enumerate(EVENT_TYPES):
                if random.random() > steps[step]:
                    break
                eid += 1
                product_id = random.choice(products)["product_id"] if event != "page_view" else 0
                w.writerow([eid, t.strftime("%Y-%m-%d %H:%M:%S"), uid, event,
                            product_id, session_id, device])
            session_id += 1


def write_orders(events_path, products):
    """Заказы порождаем из событий purchase: реалистично связывает таблицы."""
    orders_path = os.path.join(DATA_DIR, "orders.csv")
    items_path = os.path.join(DATA_DIR, "order_items.csv")
    statuses = ["paid", "shipped", "delivered", "cancelled"]
    order_id = 0
    with open(events_path, encoding="utf-8") as ev, \
         open(orders_path, "w", newline="", encoding="utf-8") as fo, \
         open(items_path, "w", newline="", encoding="utf-8") as fi:
        w_events = csv.reader(ev)
        w_orders = csv.writer(fo)
        w_items = csv.writer(fi)
        for row in w_events:
            if row[3] != "purchase":
                continue
            order_id += 1
            uid, t = int(row[2]), dt.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
            # 10% отмен
            status = random.choices(statuses, weights=[0.15, 0.25, 0.5, 0.1])[0]
            n_items = random.randint(1, 4)
            picked = random.sample(products, n_items)
            total = 0
            for p in picked:
                qty = random.choices([1, 2, 3], weights=[0.8, 0.15, 0.05])[0]
                total += p["price"] * qty
                w_items.writerow([order_id, p["product_id"], p["category"], qty, p["price"]])
            w_orders.writerow([order_id, uid, t.strftime("%Y-%m-%d %H:%M:%S"), status, total])
    return order_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=N_USERS)
    ap.add_argument("--events", type=int, default=N_EVENTS)
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    products = make_products()
    tiers = user_pool(args.users)

    write_users(os.path.join(DATA_DIR, "users.csv"), args.users)
    write_products(os.path.join(DATA_DIR, "products.csv"), products)
    write_events(os.path.join(DATA_DIR, "events.csv"), args.events, tiers, products)
    n_orders = write_orders(os.path.join(DATA_DIR, "events.csv"), products)
    print(f"Готово: {args.users} пользователей, {args.events} событий, {n_orders} заказов")


if __name__ == "__main__":
    main()
