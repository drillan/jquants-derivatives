from abc import ABC
from dataclasses import dataclass

import numpy as np


@dataclass
class Base(ABC):
    @classmethod
    def get_dtype(cls, field: str) -> str:
        return cls.__annotations__[field]


@dataclass
class IndexOption(Base):
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
    def get_dtype(cls, field: str) -> type:
        key = field.replace("(", "").replace(")", "")
        return cls.__annotations__[key]
