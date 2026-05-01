import sqlite3

import psycopg


SQLITE_DB = "data/research_hub.db"

POSTGRES_DSN = (
    "postgresql://neondb_owner:npg_1FegpKcQkCb6"
    "@ep-dry-bar-amelm6ed-pooler.c-5.us-east-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)

TABLE_ORDER = [
    "ingestion_runs",
    "source_sync_state",
    "papers",
]


def normalize_value(table: str, column: str, value):
    if table == "papers" and column == "is_fit" and value is not None:
        return bool(value)
    return value


sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

pg_conn = psycopg.connect(POSTGRES_DSN)
pg_cur = pg_conn.cursor()

pg_cur.execute('TRUNCATE TABLE "papers", "source_sync_state", "ingestion_runs" CASCADE')
pg_conn.commit()

for table in TABLE_ORDER:
    print(f"Copying table: {table}")

    sqlite_cur.execute(f'SELECT * FROM "{table}"')
    rows = sqlite_cur.fetchall()

    if not rows:
        print(f"  Skipping empty table: {table}")
        continue

    columns = rows[0].keys()
    column_list = ", ".join(f'"{col}"' for col in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})'

    values = [
        tuple(normalize_value(table, col, row[col]) for col in columns)
        for row in rows
    ]
    pg_cur.executemany(insert_sql, values)
    pg_conn.commit()

    print(f"  Inserted {len(values)} rows")

pg_cur.close()
pg_conn.close()
sqlite_conn.close()

print("Done.")
