import numpy as np

import jquants_derivatives


def test_update_sq(tmp_path):
    jquants_derivatives.database.sq_csv = tmp_path / "sq.csv"
    jquants_derivatives.database.update_sq()
    with open(jquants_derivatives.database.sq_csv, "r") as f:
        assert next(f).strip() == "ContractMonth,SpecialQuotationDay,FinalSettlementPrice"


def test_dataframe(cli):
    df = cli.get_option_index_option()
    option = jquants_derivatives.Option(df, contracts=2)
    for contract_month in option.contract_month:
        contract = option.contracts_dfs[contract_month]
        assert "FinalSettlementPrice" in contract.columns
        assert isinstance(contract.loc[:, "FinalSettlementPrice"].dtype, np.dtypes.Float64DType)