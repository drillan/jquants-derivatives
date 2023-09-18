from abc import ABC
from dataclasses import dataclass
from typing import Any, Type

import numpy as np
import pandas as pd


@dataclass
class DataFrameColumnsBase(ABC):
    @classmethod
    def get_dtype(cls, field: str) -> Type[Any]:
        return cls.__annotations__[field]


@dataclass
class IndexOption(DataFrameColumnsBase):
    Date: np.dtype("datetime64[ns]")
    Code: str
    WholeDayOpen: float
    WholeDayHigh: float
    WholeDayLow: float
    WholeDayClose: float
    NightSessionOpen: float
    NightSessionHigh: float
    NightSessionLow: float
    NightSessionClose: float
    DaySessionOpen: float
    DaySessionHigh: float
    DaySessionLow: float
    DaySessionClose: float
    Volume: float
    OpenInterest: float
    TurnoverValue: float
    ContractMonth: str
    StrikePrice: float
    VolumeOnlyAuction: float
    EmergencyMarginTriggerDivision: str
    PutCallDivision: int
    LastTradingDay: np.dtype("datetime64[ns]")
    SpecialQuotationDay: np.dtype("datetime64[ns]")
    SettlementPrice: float
    TheoreticalPrice: float
    BaseVolatility: float
    UnderlyingPrice: float
    ImpliedVolatility: float
    InterestRate: float

    @classmethod
    def get_dtype(cls, field: str) -> Type[Any]:
        key = field.replace("(", "").replace(")", "")
        return cls.__annotations__[key]


@dataclass
class IndexOptionAppend(IndexOption):
    Otm: pd.Int8Dtype()
    TimeToMaturity: np.dtype("datetime64[ns]")
    FinalSettlementPrice: float
    Delta: float
    Gamma: float
    Vega: float
    Theta: float