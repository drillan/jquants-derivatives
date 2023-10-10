from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from jquants_derivatives.models import IndexOptionAppend

from . import bsm, database

YEAR_TO_SECONDS = 31_536_000  # 365日を秒に換算


@dataclass
class Option:
    df: pd.DataFrame
    contracts: int = 2  # 扱う限月の数
    min_price: float = 1  # 扱うプレミアムの最小値
    sq: bool = True
    greeks: bool = True
    use_cache: bool = True
    cache_table_name: str = "OPTION_INDEX_OPTION_PROCESSED"

    def __post_init__(self):
        self.raw_df = self.df.copy()
        # 取引日
        self.date = self.raw_df.loc[:, "Date"].iloc[0]
        # 限月
        self.contract_month = sorted(
            self.raw_df.groupby("ContractMonth").groups.keys()
        )[: self.contracts]
        self._groupby_contract_month = (
            self.raw_df.reset_index(drop=True)
            .set_index("ContractMonth")
            .loc[self.contract_month]
            .groupby("ContractMonth")
        )
        # 原資産価格
        self.underlying_price = dict(
            self._groupby_contract_month["UnderlyingPrice"].first()
        )
        # 基準ボラティリティ
        self.base_volatility = dict(
            self._groupby_contract_month["BaseVolatility"].first()
        )
        # 理論価格計算用金利
        self.interest_rate = dict(self._groupby_contract_month["InterestRate"].first())
        # 取引最終年月日
        self.last_tradingDay = dict(
            self._groupby_contract_month["LastTradingDay"].first()
        )
        # 期間
        self.time_to_maturity = {
            contract: self.get_time_to_maturity(
                self.date, self.last_tradingDay[contract]
            )
            for contract in self.contract_month
        }
        # SQ値
        if self.sq:
            self.sq_price = self.get_sq_price()
            self.final_settlement_price = self.sq_price

        self._append_columns = ["Otm", "TimeToMaturity"]
        if self.sq:
            self._append_columns += ["FinalSettlementPrice"]
        if self.greeks:
            self._append_columns += ["Delta", "Gamma", "Vega", "Theta"]

        if self.use_cache:
            try:
                data = database.load(self.cache_table_name, str(self.date))
            except pd.errors.DatabaseError:
                data = pd.DataFrame()
            if len(data) > 0:
                self.df = data
            else:
                self.df = self.process_data()
                database.store(self.df, self.cache_table_name)
        else:
            self.df = self.process_data()
            database.store(self.df, self.cache_table_name)
        
        self.contracts_dfs = self.get_filtered_data(self.df)

    def process_data(self) -> pd.DataFrame:
        groupby_contract_month = self.raw_df.groupby("ContractMonth")
        base_df = (
            pd.concat(
                [
                    groupby_contract_month.get_group(contract)
                    for contract in self.contract_month
                ]
            )
            .sort_values(by=["ContractMonth", "PutCallDivision", "StrikePrice"])
            .reset_index(drop=True)
        )
        concat_df_series = [base_df] + [
            pd.Series(name=columns, dtype=IndexOptionAppend.get_dtype(columns))
            for columns in self._append_columns
        ]
        df = pd.concat(concat_df_series, axis=1)
        df.index = df.apply(
            lambda x: (x["ContractMonth"], x["PutCallDivision"], int(x["StrikePrice"])),
            axis=1,
        )
        # 百分率を小数に変換
        df.loc[:, ["BaseVolatility", "ImpliedVolatility", "InterestRate"]] = (
            df.loc[:, ["BaseVolatility", "ImpliedVolatility", "InterestRate"]] * 0.01
        )
        # OTM
        df["Otm"] = np.int8(0)
        # Put
        df.loc[
            (df.loc[:, "StrikePrice"] <= df.loc[:, "UnderlyingPrice"])
            & (df.loc[:, "PutCallDivision"] == 1),
            "Otm",
        ] = np.int8(1)
        # Call
        df.loc[
            (df.loc[:, "StrikePrice"] > df.loc[:, "UnderlyingPrice"])
            & (df.loc[:, "PutCallDivision"] == 2),
            "Otm",
        ] = np.int8(1)

        ix = _get_ix(df, self.contract_month)
        # 期間
        for contract in self.contract_month:
            df.loc[ix["contract"][contract], "TimeToMaturity"] = self.time_to_maturity[
                contract
            ]
        # SQ値
        if self.sq:
            for contract in self.contract_month:
                df.loc[
                    ix["contract"][contract], "FinalSettlementPrice"
                ] = self.sq_price[contract]
        # ITMのボラティリティをOTMにそろえる
        self.align_itm_from_otm(df, "ImpliedVolatility")
        # Greeks
        if self.greeks:
            apply_greeks(df, self.contract_month)

        return df

    def get_time_to_maturity(self, t0: pd.Timestamp, t1: pd.Timestamp) -> float:
        """満期までの期間（年）"""
        return (t1 - t0).total_seconds() / YEAR_TO_SECONDS

    def get_sq_price(self) -> dict[str, float]:
        """SQ値"""
        sq_ser = pd.read_csv(database.sq_csv, index_col="ContractMonth").loc[
            :, "FinalSettlementPrice"
        ]
        return dict(sq_ser.reindex(self.contract_month))

    def align_itm_from_otm(self, df: pd.DataFrame, columns_name: str) -> None:
        """ITMのデータをOTMにそろえる"""
        ix = _get_ix(df, self.contract_month)
        for contract in self.contract_month:
            df.loc[ix["itm_put"][contract], columns_name] = df.loc[
                ix["otm_call"][contract], columns_name
            ].values
            df.loc[ix["itm_call"][contract], columns_name] = df.loc[
                ix["otm_put"][contract], columns_name
            ].values

    def get_filtered_data(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        groupby_contract = df.groupby("ContractMonth")
        contracts_dfs = {
            contract: self.filter_data(groupby_contract.get_group(contract))
            for contract in self.contract_month
        }
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


def _get_ix(df: pd.DataFrame, contract_month: list) -> dict:
    ix = {}
    ix["contract"] = {
        contract: df.loc[df.loc[:, "ContractMonth"] == contract].index
        for contract in contract_month
    }
    ix["put"] = {
        contract: df.loc[
            (df.loc[:, "ContractMonth"] == contract)
            & (df.loc[:, "PutCallDivision"] == 1)
        ].index
        for contract in contract_month
    }
    ix["call"] = {
        contract: df.loc[
            (df.loc[:, "ContractMonth"] == contract)
            & (df.loc[:, "PutCallDivision"] == 2)
        ].index
        for contract in contract_month
    }
    ix["otm_put"] = {
        contract: df.loc[
            (df.loc[:, "ContractMonth"] == contract)
            & (df.loc[:, "PutCallDivision"] == 1)
            & (df.loc[:, "Otm"] == 1)
        ].index
        for contract in contract_month
    }
    ix["otm_call"] = {
        contract: df.loc[
            (df.loc[:, "ContractMonth"] == contract)
            & (df.loc[:, "PutCallDivision"] == 2)
            & (df.loc[:, "Otm"] == 1)
        ].index
        for contract in contract_month
    }
    ix["itm_put"] = {
        contract: df.loc[
            (df.loc[:, "ContractMonth"] == contract)
            & (df.loc[:, "PutCallDivision"] == 1)
            & (df.loc[:, "Otm"] == 0)
        ].index
        for contract in contract_month
    }
    ix["itm_call"] = {
        contract: df.loc[
            (df.loc[:, "ContractMonth"] == contract)
            & (df.loc[:, "PutCallDivision"] == 2)
            & (df.loc[:, "Otm"] == 0)
        ].index
        for contract in contract_month
    }
    return ix


def apply_greeks(df: pd.DataFrame, contract_month: list) -> None:
    for contract in contract_month:
        _apply_greeks(df, contract_month, contract)


def _apply_greeks(df: pd.DataFrame, contract_month: list, contract: str) -> None:
    ix = _get_ix(df, contract_month)
    # Delta put
    df.loc[ix["put"][contract], "Delta"] = df.loc[ix["put"][contract], :].apply(
        lambda x: bsm.delta_put(
            x["UnderlyingPrice"],
            x["StrikePrice"],
            x["TimeToMaturity"],
            x["InterestRate"],
            x["ImpliedVolatility"],
        ),
        axis=1,
    )
    # Delta Call
    df.loc[ix["call"][contract], "Delta"] = df.loc[ix["call"][contract], :].apply(
        lambda x: bsm.delta_call(
            x["UnderlyingPrice"],
            x["StrikePrice"],
            x["TimeToMaturity"],
            x["InterestRate"],
            x["ImpliedVolatility"],
        ),
        axis=1,
    )
    # Gamma
    df.loc[ix["contract"][contract], "Gamma"] = df.loc[
        ix["contract"][contract], :
    ].apply(
        lambda x: bsm.gamma(
            x["UnderlyingPrice"],
            x["StrikePrice"],
            x["TimeToMaturity"],
            x["InterestRate"],
            x["ImpliedVolatility"],
        ),
        axis=1,
    )
    # Vega
    df.loc[ix["contract"][contract], "Vega"] = df.loc[
        ix["contract"][contract], :
    ].apply(
        lambda x: bsm.vega(
            x["UnderlyingPrice"],
            x["StrikePrice"],
            x["TimeToMaturity"],
            x["InterestRate"],
            x["ImpliedVolatility"],
        ),
        axis=1,
    )
    # Theta put
    df.loc[ix["put"][contract], "Theta"] = df.loc[ix["put"][contract], :].apply(
        lambda x: bsm.theta_put(
            x["UnderlyingPrice"],
            x["StrikePrice"],
            x["TimeToMaturity"],
            x["InterestRate"],
            x["ImpliedVolatility"],
        ),
        axis=1,
    )
    # Theta Call
    df.loc[ix["call"][contract], "Theta"] = df.loc[ix["call"][contract], :].apply(
        lambda x: bsm.theta_call(
            x["UnderlyingPrice"],
            x["StrikePrice"],
            x["TimeToMaturity"],
            x["InterestRate"],
            x["ImpliedVolatility"],
        ),
        axis=1,
    )


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
