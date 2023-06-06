import sqlite3
from pathlib import Path

import jquantsapi
import pandas as pd

directory = Path.home() / ".jquants-api"
db = directory / "jquantsapi.db"


def generate_table_sql(constant: str) -> str:
    table_name = constant.replace("_COLUMNS", "")
    fields = getattr(jquantsapi.constants, constant)
    fields_sql = ", ".join((f'"{x}"' for x in fields))
    return f"CREATE TABLE IF NOT EXISTS {table_name} ({fields_sql})"


def create_tables() -> None:
    constants = (x for x in dir(jquantsapi.constants) if x.endswith("_COLUMNS"))
    sqls = (generate_table_sql(constant) for constant in constants)
    for sql in sqls:
        with sqlite3.connect(db) as con:
            cur = con.cursor()
            cur.execute(sql)
            con.commit()


def store(df: pd.DataFrame, table: str) -> None:
    with sqlite3.connect(db) as con:
        df.to_sql(table, con, if_exists="append", index=False)


def load(table: str, date_yyyymmdd: str) -> pd.DataFrame:
    date = pd.Timestamp(date_yyyymmdd)
    with sqlite3.connect(db) as con:
        sql = f'SELECT * FROM {table} WHERE Date = "{date}"'
        return pd.read_sql(sql, con)


def main() -> None:
    if not db.exists():
        directory.mkdir(exist_ok=True)
        create_tables()


if __name__ == "__main__":
    main()
