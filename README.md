# ETL-пайплайн «Продажи» — Kafka + ClickHouse

Потоковый ETL-проект: события продаж проходят через Apache Kafka, очищаются
и агрегируются в ClickHouse. Написан на Python + pandas 

## Архитектура

```
producer.py ──► [sales.raw] ──► etl_consumer.py ──► [sales.clean] ──► clickhouse_sink.py
                                        │                                    │
                                        └──► [sales.dead] (DLQ)              ▼
                                                            shop.stg_sales_clean (ReplacingMergeTree)
                                                            shop.mart_sales_monthly (REPLACE PARTITION)
```

Топики:

- `sales.raw` — сырые события от продюсера;
- `sales.clean` — очищенные и обогащённые записи;
- `sales.dead` — DLQ: непрошедшие валидацию события с указанием причины;
- `sales.mart` — агрегаты витрины (в эмуляции брокера).

## Состав проекта

| Файл | Назначение |
|---|---|
| `main.py` | Точка входа: продюсер → consumer → загрузка в ClickHouse → пересборка витрины |
| `producer.py` | Генерация 23 синтетических событий с намеренной «грязью» и отправка в `sales.raw` |
| `etl_consumer.py` | Стрим-процессор: валидация, дедупликация, DLQ |
| `transform.py` | Правила чистки: парсинг сумм и дат, нормализация, дедуп, агрегация |
| `ddl.py` | DDL и SQL ClickHouse (единый источник схемы) |
| `clickhouse_sink.py` | Загрузка в ClickHouse и идемпотентная пересборка витрины |
| `config.py` | Конфигурация: топики, адреса, константы |
| `customer_ref.py` | Справочник клиентов (имитация внешнего API) |
| `broker.py` | Абстракция брокера: реальный Kafka или in-memory эмуляция |
| `test_transform.py` | 21 юнит-тест на правила трансформации |
| `local_demo.py` | Контрольный прогон без Docker и ClickHouse |
| `docker-compose.yml` | Kafka (KRaft, без Zookeeper) + ClickHouse 24.8 |
| `requirements.txt` | Зависимости |
| `.gitignore` | Игнор-лист (базы, кэш, venv) |


`local_demo.py` поднимает всю логику на эмуляции брокера — Kafka и
ClickHouse для проверки трансформаций не нужны.

## ClickHouse-схема

- **stg_sales_clean** — `ReplacingMergeTree(updated_at)`, `ORDER BY (order_id)`:
  идемпотентные вставки, дедупликация и last-write-wins на уровне движка,
  чтение через `FINAL`;
- **dim_customers** — `ReplacingMergeTree` по `customer_id`;
- **mart_sales_monthly** — `MergeTree` с партиционированием по месяцу;
  пересборка через `INSERT` во временную таблицу + `ALTER ... REPLACE PARTITION`,
  поэтому перезапуск пайплайна не дублирует агрегаты.

Типы: `LowCardinality(String)` для категорий и сегментов, `Decimal(12, 2)`
для денег, `DateTime64` для событий.

## Правила трансформации

- `amount`: строка вида `"12 990 руб."` → `12990.0` (учёт неразрывных
  пробелов, запятой как разделителя, суффикса «руб.»); нулевые,
  отрицательные и нечисловые значения → DLQ;
- дубликаты `order_id`: остаётся версия с максимальным `ts`
  (last-write-wins); вторая линия обороны — `ReplacingMergeTree`;
- витрина считает выручку только по `status = 'paid'` (`refunded` и
  `canceled` не учитываются);
- enrichment: к продаже добавляется сегмент клиента из справочника.

## Результат контрольного прогона

23 сырых события → 15 очищенных, 3 дубликата отброшено, 5 событий в DLQ
с причинами отбраковки; витрина — 10 строк агрегатов (например,
«Техника / VIP: 3 заказа, выручка 18 060,40»).

## Сознательные упрощения

- дедуп-состояние consumer'а хранится в памяти процесса (в проде —
  Kafka Streams или внешнее хранилище состояния);
- JSON вместо Avro / Schema Registry;
- семантика at-least-once, не exactly-once;
- одна consumer-группа.

