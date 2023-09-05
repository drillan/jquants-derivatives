from dataclasses import dataclass
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

YEAR_TO_SECONDS = 31_536_000  # 365日を秒に換算


@dataclass
class Option:
    df: pd.DataFrame
    contracts: int = 2  # 扱う限月の数
    min_price: float = 1  # 扱うプレミアムの最小値

    def __post_init__(self):
        self.date = self.df.loc[:, "Date"].iloc[0]
        self._groupby_contract_month: pd.core.groupby.generic.DataFrameGroupBy = (
            self.df.groupby("ContractMonth")
        )
        self.contract_month: list = sorted(self._groupby_contract_month.groups.keys())[
            : self.contracts
        ][: self.contracts]
        self.contracts_dfs: dict[str, pd.DataFrame] = self.get_processed_data()
        self.underlying_price: dict[str, float] = self.get_common_value(
            "UnderlyingPrice"
        )
        self.base_volatility: dict[str, float] = self.get_common_value("BaseVolatility")
        self.interest_rate: dict[str, float] = self.get_common_value("InterestRate")
        self.last_tradingDay: dict[str, pd.Timestamp] = self.get_common_value(
            "LastTradingDay"
        )
        self.special_quotationDay: dict[str, pd.Timestamp] = self.get_common_value(
            "SpecialQuotationDay"
        )
        self.time_to_maturity = {
            contract_month: self.get_time_to_maturity(
                self.date, self.special_quotationDay[contract_month]
            )
            for contract_month in self.contract_month
        }

    def get_processed_data(self) -> dict[str, pd.DataFrame]:
        contracts_dfs = {
            contract: self.filter_data(self._groupby_contract_month.get_group(contract))
            for contract in self.contract_month
        }
        for key in contracts_dfs:
            contracts_dfs[key] = self.percentage_to_decimal(contracts_dfs[key])
        return contracts_dfs

    def filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """扱うストライクだけを抽出する"""
        s = df.loc[:, "UnderlyingPrice"].iloc[0]  # 原資産価格
        # 取引高が0のストライクを除外
        volume_exists = df.loc[df.loc[:, "Volume"] != 0, :].sort_values("StrikePrice")
        # OTMを抽出、ATMとストライクが同値の場合はプット型に寄せる
        put = volume_exists.loc[
            (volume_exists.loc[:, "PutCallDivision"] == 1)
            & (volume_exists.loc[:, "WholeDayClose"] != 0)
            & (volume_exists.loc[:, "StrikePrice"] <= s)
        ]
        call_ = volume_exists.loc[
            (volume_exists.loc[:, "PutCallDivision"] == 2)
            & (volume_exists.loc[:, "WholeDayClose"] != 0)
            & (volume_exists.loc[:, "StrikePrice"] > s)
        ]
        # 扱うストライクをプレミアムの最小値までとする
        min_price_put = max(put.loc[:, "WholeDayClose"].min(), self.min_price)
        price_min_strike_put = put.loc[
            put.loc[:, "WholeDayClose"] == min_price_put, "StrikePrice"
        ].max()
        min_price_call = max(call_.loc[:, "WholeDayClose"].min(), self.min_price)
        price_min_strike_call = call_.loc[
            call_.loc[:, "WholeDayClose"] == min_price_call, "StrikePrice"
        ].min()
        filtered_put = put.loc[put.loc[:, "StrikePrice"] >= price_min_strike_put, :]
        filtered_call = call_.loc[
            call_.loc[:, "StrikePrice"] <= price_min_strike_call, :
        ]
        return pd.concat([filtered_put, filtered_call], ignore_index=True).sort_values(
            "StrikePrice"
        )

    def percentage_to_decimal(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = "BaseVolatility", "ImpliedVolatility", "InterestRate"

        def to_decimal(col: str, ser: pd.Series) -> pd.Series:
            if col in cols:
                return ser * 0.01
            else:
                return ser

        return pd.DataFrame(
            {col: to_decimal(col, df.loc[:, col]) for col in df.columns}
        )

    def get_common_value(self, value: str) -> dict:
        return {
            contract: self.contracts_dfs[contract].loc[:, value].iloc[0]
            for contract in self.contracts_dfs
        }

    def get_time_to_maturity(self, t0: pd.Timestamp, t1: pd.Timestamp) -> float:
        return (t1 - t0).total_seconds() / YEAR_TO_SECONDS


def plot_volatility(
    option: Option,
    option_other: Optional[Option] = None,
    colors: list = px.colors.qualitative.Dark2,
) -> go.Figure:
    date = f"{option.date: %Y/%m/%d}"
    underlying_price = {k: round(v, 2) for k, v in option.underlying_price.items()}
    base_volatility = {k: round(v, 4) for k, v in option.base_volatility.items()}
    layout = go.Layout(
        title={
            "text": f"Date: {date}, UnderlyingPrice: {underlying_price}, BaseVolatility: {base_volatility}"
        }
    )
    fig = go.Figure(layout=layout)
    for i, (contract, df) in enumerate(option.contracts_dfs.items()):
        fig.add_trace(
            go.Scatter(
                go.Scatter(
                    x=df.loc[:, "StrikePrice"], y=df.loc[:, "ImpliedVolatility"]
                ),
                name=contract,
                line={"color": colors[i]},
            )
        )
    if option_other:
        for i, (contract, df) in enumerate(option_other.contracts_dfs.items()):
            fig.add_trace(
                go.Scatter(
                    go.Scatter(
                        x=df.loc[:, "StrikePrice"], y=df.loc[:, "ImpliedVolatility"]
                    ),
                    name=contract,
                    line={"color": colors[i], "dash": "dashdot"},
                )
            )
    s = sorted(option.underlying_price.values())
    s0, s1 = s[0], s[-1]
    fig.add_vrect(x0=s0, x1=s1, opacity=0.8)
    if option_other:
        s_other = sorted(option_other.underlying_price.values())
        s_other0, s_other1 = s_other[0], s_other[-1]
        fig.add_vrect(x0=s_other0, x1=s_other1, opacity=0.3)
    return fig
