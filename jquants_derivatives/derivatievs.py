from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import database
from . import bsm

YEAR_TO_SECONDS = 31_536_000  # 365日を秒に換算
MAX_POSITIONS = 10000


@dataclass
class Option:
    df: pd.DataFrame
    contracts: int = 2  # 扱う限月の数
    min_price: float = 1  # 扱うプレミアムの最小値
    sq: bool = True
    greeks: bool = True

    def __post_init__(self):
        self.raw_df = self.df
        self.date = self.df.loc[:, "Date"].iloc[0]
        self._groupby_contract_month = self.df.groupby("ContractMonth")
        self.contract_month = sorted(self._groupby_contract_month.groups.keys())[
            : self.contracts
        ][: self.contracts]
        self.contracts_dfs = self.get_filtered_data()
        self.underlying_price = self.get_common_value("UnderlyingPrice")
        self.base_volatility = self.get_common_value("BaseVolatility")
        self.interest_rate = self.get_common_value("InterestRate")
        self.last_tradingDay = self.get_common_value("LastTradingDay")
        self.special_quotationDay = self.get_common_value("SpecialQuotationDay")
        self.time_to_maturity = {
            contract_month: self.get_time_to_maturity(
                self.date, self.special_quotationDay[contract_month]
            )
            for contract_month in self.contract_month
        }
        self.sq_price = pd.read_csv(database.sq_csv).loc[
            :, ["ContractMonth", "FinalSettlementPrice"]
        ]
        self.df = pd.concat(
            [self.get_processed_data(contract) for contract in self.contract_month]
        )
        if self.sq:
            for contract in self.contract_month:
                self.contracts_dfs[contract] = self.append_sq(
                    self.contracts_dfs[contract]
                )
        if self.greeks:
            for contract in self.contract_month:
                greeks_df = self.make_greeks_df(contract)
                self.contracts_dfs[contract] = pd.concat(
                    [self.contracts_dfs[contract], greeks_df], axis=1
                )
        self.final_settlement_price: dict[str, float] = self.get_common_value(
            "FinalSettlementPrice"
        )

    def get_filtered_data(self) -> dict[str, pd.DataFrame]:
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

    def append_sq(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.merge(
            df,
            self.sq_price,
            on="ContractMonth",
            how="left",
        )

    def get_put_call_data(self, contract: str, division: int):
        df = (
            (
                self._groupby_contract_month.get_group(contract)
                .groupby("PutCallDivision")
                .get_group(division)
            )
            .set_index("StrikePrice", drop=False)
            .sort_index()
        )
        df.loc[df.loc[:, "TheoreticalPrice"] < 1, "TheoreticalPrice"] = 0
        return df

    def get_processed_data(self, contract: str):
        put = self.get_put_call_data(contract, 1)
        call = self.get_put_call_data(contract, 2)
        atm = self.underlying_price[contract]
        otm_put = put.index[put.index <= atm]
        otm_call = call.index[call.index > atm]
        itm_put = put.index[put.index >= atm]
        itm_call = call.index[call.index < atm]
        put.loc[itm_put, "ImpliedVolatility"] = call.loc[otm_call, "ImpliedVolatility"]
        call.loc[itm_call, "ImpliedVolatility"] = put.loc[otm_put, "ImpliedVolatility"]
        put.index = put.apply(
            lambda x: f"{x['ContractMonth']},{int(x['StrikePrice'])},{x['PutCallDivision']}",
            axis=1,
        )
        call.index = call.apply(
            lambda x: f"{x['ContractMonth']},{int(x['StrikePrice'])},{x['PutCallDivision']}",
            axis=1,
        )
        df = pd.concat([put, call]).assign(
            TimeToMaturity=self.time_to_maturity[contract]
        )
        df_with_sq = self.append_sq(df)
        df_with_sq.index = pd.MultiIndex.from_frame(
            df_with_sq.loc[:, ["ContractMonth", "PutCallDivision", "StrikePrice"]]
        )
        return df_with_sq

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

    def make_greeks_df(self, contract: str) -> pd.DataFrame:
        df = self.contracts_dfs[contract]
        groupby_div = df.groupby("PutCallDivision")
        put_df = groupby_div.get_group(1)
        call_df = groupby_div.get_group(2)
        s = self.underlying_price[contract]
        t = self.time_to_maturity[contract]
        r = self.interest_rate[contract]
        k = df.loc[:, "StrikePrice"]
        k_put = put_df.loc[:, "StrikePrice"]
        k_call = call_df.loc[:, "StrikePrice"]
        sigma = df.loc[:, "ImpliedVolatility"]
        sigma_put = put_df.loc[:, "ImpliedVolatility"]
        sigma_call = call_df.loc[:, "ImpliedVolatility"]
        greeks = {}
        delta_put = bsm.delta_put(s, k_put, t, r, sigma_put)
        delta_call = bsm.delta_call(s, k_call, t, r, sigma_call)
        greeks["Delta"] = np.concatenate([delta_put, delta_call])
        greeks["Gamma"] = bsm.gamma(s, k, t, r, sigma)
        greeks["Vega"] = bsm.vega(s, k, t, r, sigma)
        theta_put = bsm.theta_put(s, k_put, t, r, sigma_put)
        theta_call = bsm.theta_call(s, k_call, t, r, sigma_call)
        greeks["Theta"] = np.concatenate([theta_put, theta_call])
        return pd.DataFrame(greeks, index=df.index)


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


@dataclass
class Position:
    option: Option

    def __post_init__(self):
        columns = list(self.option.contracts_dfs[self.option.contract_month[0]].columns)
        columns += ["Quantity", "ExecutionPrice"]
        self.position_df = pd.DataFrame([], columns=columns)
        self.id = self.gen_id()

    def gen_id(self):
        for i in range(MAX_POSITIONS):
            yield i

    def add_position(
        self,
        contract_month: str,
        put_call_division: int,
        strike_price: float = None,
        quantity: float = 0,
        execution_price=0,
    ):
        position_id = next(self.id)
        data = pd.concat(
            [
                self.option.df.loc[(contract_month, put_call_division, strike_price)],
                pd.Series(
                    [quantity, execution_price], index=["Quantity", "ExecutionPrice"]
                ),
            ]
        )
        data_with_greeks = self.append_greeks(data)
        self.position_df.loc[position_id] = data_with_greeks

    def append_greeks(self, data: pd.Series) -> pd.Series:
        data_with_greeks = data.copy()
        delta = bsm.delta(
            data["UnderlyingPrice"],
            data["StrikePrice"],
            data["TimeToMaturity"],
            data["InterestRate"],
            data["ImpliedVolatility"],
            data["PutCallDivision"],
        )
        gamma = bsm.gamma(
            data["UnderlyingPrice"],
            data["StrikePrice"],
            data["TimeToMaturity"],
            data["InterestRate"],
            data["ImpliedVolatility"],
        )
        vega = bsm.vega(
            data["UnderlyingPrice"],
            data["StrikePrice"],
            data["TimeToMaturity"],
            data["InterestRate"],
            data["ImpliedVolatility"],
        )
        theta = bsm.theta(
            data["UnderlyingPrice"],
            data["StrikePrice"],
            data["TimeToMaturity"],
            data["InterestRate"],
            data["ImpliedVolatility"],
            data["PutCallDivision"],
        )
        data_with_greeks.loc["Delta"] = delta
        data_with_greeks.loc["Gamma"] = gamma
        data_with_greeks.loc["Vega"] = vega
        data_with_greeks.loc["Theta"] = theta
        return data_with_greeks
