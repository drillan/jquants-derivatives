from functools import wraps
from typing import Type

import jquantsapi
import numpy as np
import pandas as pd

from . import database
from .models import IndexOption


def cache(table_name: str):
    """関数が実行して返したDataFrameをsqlite3のデータベースに保管"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, date_yyyymmdd: str):
            df = database.load(table_name, date_yyyymmdd)
            if len(df) > 0:
                return df
            else:
                df = func(self, date_yyyymmdd)
                database.store(df, table_name)
                return df

        return wrapper

    return decorator


def cast_dataframe(data_class):
    def decorator(func):
        @wraps(func)
        def wrapper(self, date_yyyymmdd: str):
            print("called")
            df = func(self, date_yyyymmdd)
            return pd.DataFrame(
                {
                    col: cast_series_dtype(df.loc[:, col], data_class.get_dtype(col))
                    for col in df.columns
                }
            )

        return wrapper

    return decorator


def cast_series_dtype(ser: pd.Series, dtype: type) -> pd.Series:
    """Seriesのデータ型を変換"""
    if np.issubdtype(dtype, np.number):
        return pd.to_numeric(ser, errors="coerce").astype(dtype)
    elif np.issubdtype(dtype, np.datetime64):
        return pd.to_datetime(ser)
    else:
        return ser.astype(dtype)


def cast_dataframe_dtype(
    df: pd.DataFrame, data_class: Type[IndexOption]
) -> pd.DataFrame:
    """DataFrameのデータ型をmodelsで定義したクラスの型に変換"""
    return pd.DataFrame(
        {
            col: cast_series_dtype(df.loc[:, col], data_class.get_dtype(col))
            for col in df.columns
        }
    )


class Client(jquantsapi.Client):
    def __init__(self):
        super().__init__()

    @cache("OPTION_INDEX_OPTION")
    def get_option_index_option(self, *args, **kwargs) -> pd.DataFrame:
        return super().get_option_index_option(*args, **kwargs)

    def get_option_index_option_processed(self, date_yyyymmdd: str) -> pd.DataFrame:
        df = self.get_option_index_option(date_yyyymmdd)
        casted_df = cast_dataframe_dtype(df, IndexOption)
        return casted_df
