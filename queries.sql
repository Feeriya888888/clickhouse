-- =============================================================
--  Аналитические запросы к хранилищу
-- =============================================================

-- 1. DAU по дням (уникальные пользователи)
SELECT
    toDate(event_time) AS day,
    uniqExact(user_id) AS dau
FROM shop.events
WHERE event_time >= now() - INTERVAL 90 DAY
GROUP BY day
ORDER BY day;

-- 2. Воронка конверсии за 30 дней: просмотр -> корзина -> оформление -> покупка
SELECT
    countIf(event_type = 'product_view')  AS product_views,
    countIf(event_type = 'add_to_cart')   AS add_to_cart,
    countIf(event_type = 'checkout')      AS checkouts,
    countIf(event_type = 'purchase')      AS purchases,
    round(purchases / product_views * 100, 2) AS cr_percent
FROM shop.events
WHERE event_time >= now() - INTERVAL 30 DAY;

-- 3. Когортный retention (8 недель) по дате регистрации
WITH cohorts AS
(
    SELECT user_id, toMonday(signup_date) AS cohort_week
    FROM shop.users
)
SELECT
    c.cohort_week,
    floor(dateDiff('week', c.cohort_week, toDate(e.event_time))) AS week_n,
    uniqExact(e.user_id) AS active_users
FROM cohorts c
INNER JOIN shop.events e USING (user_id)
GROUP BY c.cohort_week, week_n
HAVING week_n >= 0 AND week_n <= 8
ORDER BY c.cohort_week, week_n;

-- 4. Топ-10 товаров по выручке за 30 дней
SELECT
    p.name,
    p.category,
    sum(i.price * i.quantity) AS revenue,
    sum(i.quantity)           AS units_sold
FROM shop.orders o
INNER JOIN shop.order_items i USING (order_id)
INNER JOIN shop.products p   ON p.product_id = i.product_id
WHERE o.order_time >= now() - INTERVAL 30 DAY
  AND o.status != 'cancelled'
GROUP BY p.name, p.category
ORDER BY revenue DESC
LIMIT 10;

-- 5. Выручка по городам и источникам трафика
SELECT
    u.city,
    u.traffic_source,
    toStartOfMonth(o.order_time) AS month,
    round(sum(o.total_amount), 2) AS revenue
FROM shop.orders o
INNER JOIN shop.users u USING (user_id)
WHERE o.status IN ('paid', 'shipped', 'delivered')
GROUP BY u.city, u.traffic_source, month
ORDER BY revenue DESC;

-- 6. Точность vs скорость: uniqExact (точный) и uniq (HyperLogLog-приближение)
SELECT uniqExact(user_id) AS exact, uniq(user_id) AS approx
FROM shop.events
WHERE event_time >= now() - INTERVAL 7 DAY;

-- 7. Предагрегация DAU через материализованное представление
CREATE TABLE IF NOT EXISTS shop.dau_daily
(
    day Date,
    dau AggregateFunction(uniqExact, UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY day AS
SELECT
    toDate(event_time) AS day,
    uniqExactState(user_id) AS dau
FROM shop.events
GROUP BY day;

-- Читаем агрегат:
SELECT day, uniqExactMerge(dau) AS dau
FROM shop.dau_daily
GROUP BY day
ORDER BY day;
