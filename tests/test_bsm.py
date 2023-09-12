import numpy as np

from jquants_derivatives import Option, bsm, client, models


def test_bsm(cli):
    df = cli.get_option_index_option()
    option = Option(df, contracts=2)
    implied_volatility_put = np.vectorize(bsm.implied_volatility_put)
    implied_volatility_call = np.vectorize(bsm.implied_volatility_call)

    contract = "2023-01"
    data = option.contracts_dfs[contract]
    over_5 = data.loc[data.loc[:, "TheoreticalPrice"] >= 5, :]
    groupby_div = over_5.groupby("PutCallDivision")
    put = groupby_div.get_group(1)
    call_ = groupby_div.get_group(2)
    s = option.underlying_price[contract]
    r = option.interest_rate[contract]
    t = option.time_to_maturity[contract]
    k_put = put.loc[:, "StrikePrice"]
    k_call = call_.loc[:, "StrikePrice"]
    price_put = put.loc[:, "TheoreticalPrice"]
    price_call = call_.loc[:, "TheoreticalPrice"]
    sigma_put = put.loc[:, "ImpliedVolatility"]
    sigma_call = call_.loc[:, "ImpliedVolatility"]
    np.testing.assert_array_almost_equal(
        implied_volatility_put(s, k_put, t, r, price_put), sigma_put.values, decimal=2
    )
    np.testing.assert_array_almost_equal(
        implied_volatility_call(s, k_call, t, r, price_call), sigma_call.values, decimal=2
    )
    np.testing.assert_array_almost_equal(
        bsm.price_put(s, k_put, t, r, sigma_put), price_put.values, decimal=1
    )
    np.testing.assert_array_almost_equal(
        bsm.price_call(s, k_call, t, r, sigma_call), price_call.values, decimal=1
    )
