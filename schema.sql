-- =============================================================
--  Схема аналитического хранилища интернет-магазина (ClickHouse)
--  Задача: анализ поведения пользователей и продаж
-- =============================================================

CREATE DATABASE IF NOT EXISTS shop;

-- Пользователи
CREATE TABLE IF NOT EXISTS shop.users
(
    user_id        UInt64,
    city           LowCardinality(String),
    signup_date    Date,
    traffic_source LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY user_id;

-- События веб-аналитики
-- Партиционирование по месяцам: почти все запросы режут данные по диапазону дат
CREATE TABLE IF NOT EXISTS shop.events
(
    event_id   UInt64,
    event_time DateTime,
    user_id    UInt64,
    event_type Enum8('page_view' = 1, 'product_view' = 2, 'add_to_cart' = 3, 'checkout' = 4, 'purchase' = 5),
    product_id UInt32 DEFAULT 0,
    session_id UInt64,
    device     Enum8('desktop' = 1, 'mobile' = 2, 'tablet' = 3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, user_id)
TTL toDateTime(event_time) + INTERVAL 24 MONTH
SETTINGS index_granularity = 8192;

-- Заказы (фактовая таблица, обновления не требуются)
CREATE TABLE IF NOT EXISTS shop.orders
(
    order_id     UInt64,
    user_id      UInt64,
    order_time   DateTime,
    status       Enum8('created' = 1, 'paid' = 2, 'shipped' = 3, 'delivered' = 4, 'cancelled' = 5),
    total_amount Decimal(12, 2)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(order_time)
ORDER BY (order_time, order_id);

-- Позиции заказов
CREATE TABLE IF NOT EXISTS shop.order_items
(
    order_id   UInt64,
    product_id UInt32,
    category   LowCardinality(String),
    quantity   UInt16,
    price      Decimal(10, 2)
)
ENGINE = MergeTree
ORDER BY (order_id, product_id);

-- Товары (справочник)
CREATE TABLE IF NOT EXISTS shop.products
(
    product_id UInt32,
    name       String,
    category   LowCardinality(String),
    price      Decimal(10, 2)
)
ENGINE = MergeTree
ORDER BY product_id;
