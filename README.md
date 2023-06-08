# jquants-derivatives

[![PyPI version](https://badge.fury.io/py/jquants-derivatives.svg)](https://badge.fury.io/py/jquants-derivatives)

個人投資家向けデータ API 配信サービス「 [J-Quants API](https://jpx-jquants.com/#jquants-api) 」の [Python クライアントライブラリ](https://github.com/J-Quants/jquants-api-client-python) のデリバティブ用ラッパーです。

jquants-derivatives ではオプションのデータを利用するため、J-Quants APIのスタンダード以上のプランが必要です。

J-Quants や API 仕様についての詳細を知りたい方は [公式ウェブサイト](https://jpx-jquants.com/) をご参照ください。
現在、J-Quants API は有償版サービスとして提供されています。

## インストール方法

`pip` コマンドでインストールします。

```bash
pip install jquants-derivatives
```

### J-Quants API の利用

To use J-Quants API, you need to "Applications for J-Quants API" from [J-Quants API Web site](https://jpx-jquants.com/?lang=en) and to select a plan.

J-Quants API を利用するためには[J-Quants API の Web サイト](https://jpx-jquants.com/) から「J-Quants API 申し込み」及び利用プランの選択が必要になります。

jquants-api-client-python を使用するためには「J-Quants API ログインページで使用するメールアドレスおよびパスワード」または「J-Quants API メニューページから取得したリフレッシュトークン」が必要になります。必要に応じて下記の Web サイトより取得してください。

[J-Quants API ログインページ](https://jpx-jquants.com/auth/signin/)

## 認証設定

コードを実行する前に認証設定をしておきます。設定方法は [jquants-api-clientの設定](https://github.com/J-Quants/jquants-api-client-python#%E8%A8%AD%E5%AE%9A) を参照してください。


[Google Colab](https://colab.research.google.com/) を利用する場合は [jquants-api-clientのサンプルノートブック](https://github.com/J-Quants/jquants-api-client-python/tree/main/examples#google-colab) を参考にしてください。

## 使用方法

### Clientクラス

`jquants_derivatives.Client` クラスは `jquantsapi.Client` クラスを継承しています。
[
jquants-api-client-python](https://github.com/J-Quants/jquants-api-client-python) の `Client` クラスと同じ方法で `pandas.DataFrame` を取得します。

```python
import jquants_derivatives

cli = jquants_derivatives.Client()
df_20230605 = cli.get_option_index_option("2023-06-05")
df_20230605.iloc[:3, :6]
```

|    | Date                |      Code |   WholeDayOpen |   WholeDayHigh |   WholeDayLow |   WholeDayClose |
|---:|:--------------------|----------:|---------------:|---------------:|--------------:|----------------:|
|  0 | 2023-06-05 00:00:00 | 130060018 |              0 |              0 |             0 |               0 |
|  1 | 2023-06-05 00:00:00 | 130060218 |              0 |              0 |             0 |               0 |
|  2 | 2023-06-05 00:00:00 | 130060518 |              0 |              0 |             0 |               0 |

同じデータを取得した場合、データはsqlite3のデータベースにキャッシュされるため、2回目以降の実行ではキャッシュされたデータをもとに DataFrame を返します。

```python
%%time
df_20230605 = cli.get_option_index_option("2023-06-05")
```

```
CPU times: user 289 ms, sys: 194 ms, total: 483 ms
Wall time: 482 ms
```

キャッシュされたデータは `${HOME}/.jquants-api/jquantsapi.db` に格納されます。

次のようにSQLを使ってデータを取得できます。
IPythonまたはノートブック（Jupyter/Colabなど）からSQLを実行する場合は [ipython-sql](https://jupyter-tutorial.readthedocs.io/en/stable/data-processing/postgresql/ipython-sql.html) をインストールし、ロードします。

```bash
pip install ipython-sql
```

```
%load_ext sql
```

キャッシュの保存先を確認します。

```python
print(jquants_derivatives.database.db)
```

```
/your_home_dir/.jquants-api/jquantsapi.db
```

DBに接続し、SQLを実行します。

```
%sql sqlite:////your_home_dir/.jquants-api/jquantsapi.db
```

```
%sql SELECT name FROM sqlite_master WHERE type='table';
```

|    | name                        |
|---:|:----------------------------|
|  0 | FINS_ANNOUNCEMENT           |
|  1 | FINS_DIVIDEND               |
|  2 | FINS_STATEMENTS             |
|  3 | INDICES_TOPIX               |
|  4 | LISTED_INFO                 |
|  5 | MARKETS_BREAKDOWN           |
|  6 | MARKET_SEGMENT              |
|  7 | MARKET_SHORT_SELLING        |
|  8 | OPTION_INDEX_OPTION         |
|  9 | PRICES_DAILY_QUOTES         |
| 10 | PRICES_DAILY_QUOTES_PREMIUM |
| 11 | PRICES_PRICES_AM            |
| 12 | SECTOR_17                   |
| 13 | SECTOR_33                   |

```
%sql SELECT UnderlyingPrice from OPTION_INDEX_OPTION LIMIT 3;
```

|    |   UnderlyingPrice |
|---:|------------------:|
|  0 |           29520.1 |
|  1 |           29520.1 |
|  2 |           29520.1 |

### Optionクラス

`jquants_derivatives.Option` クラスはAPIから得られたオプションのデータを整形し、実務上扱いやすい形式に変換するクラスです。引数には `get_option_index_option` メソッドで取得した DataFrme を渡します。引数 `contracts` には対象とする限月数を渡します（デフォルトは2）。

```python
op_20230605 = Option(df_20230605, contracts=2)
```

`contract_month` 属性は限月（ContractMonth）のリストを返します。

```python
op_20230605.contract_month
```

```python
['2023-06', '2023-07']
```


`underlying_price` 属性は限月ごとの原資産価格（UnderlyingPrice）の辞書を返します。

```python
op_20230605.underlying_price
```

```python
{'2023-06': 32217.43, '2023-07': 32217.43}
```

`base_volatility` 属性は限月ごとの基準ボラティリティ（BaseVolatility）の辞書を返します。

```python
op_20230605.base_volatility
```

```python
{'2023-06': 0.1951205, '2023-07': 0.1951205}
```

`op_2023060.interest_rate` 属性は限月ごとの理論価格計算用金利（InterestRate）の辞書を返します。

```python
op_20230605.interest_rate
```

```python
{'2023-06': -0.000664, '2023-07': 0.000455}
```

`contracts_dfs` 属性は限月ごとの次の処理をした DataFrame を返します。

- 取引高（Volume）が0のデータを除外
- ITMのデータを除外し、OTMのデータを抽出
- プレミアム（WholeDayClose）の最小値（デフォルトは1）までとし、最小値よりアウト型のデータを除外

```python
op_20230605.contracts_dfs["2023-06"].iloc[:3, :5]
```

|    | Date                |      Code |   WholeDayOpen |   WholeDayHigh |   WholeDayLow |
|---:|:--------------------|----------:|---------------:|---------------:|--------------:|
|  0 | 2023-06-05 00:00:00 | 138067618 |              3 |              3 |             1 |
|  1 | 2023-06-05 00:00:00 | 188067718 |              3 |              4 |             1 |
|  2 | 2023-06-05 00:00:00 | 138067818 |              3 |              4 |             2 |


```python
op_20230605.contracts_dfs["2023-07"].iloc[:3, :5]
```

|    | Date                |      Code |   WholeDayOpen |   WholeDayHigh |   WholeDayLow |   WholeDayClose |   NightSessionOpen |
|---:|:--------------------|----------:|---------------:|---------------:|--------------:|----------------:|-------------------:|
|  0 | 2023-06-05 00:00:00 | 138067618 |              3 |              3 |             1 |               1 |                  3 |
|  1 | 2023-06-05 00:00:00 | 188067718 |              3 |              4 |             1 |               2 |                  3 |
|  2 | 2023-06-05 00:00:00 | 138067818 |              3 |              4 |             2 |               2 |                  3 |

### ボラティリティの可視化

`plot_volatility` 関数はボラティリティスマイルを可視化します。引数には `Option` クラスのインスタンスを渡します。

```python
jquants_derivatives.plot_volatility(op_20230605)
```

![op_20230605](./docs/images/op_20230605.png)

```python
op_2023060 = Option(df_20230605, contracts=2)
```

複数の時間帯を比較して可視化するには、 `plot_volatility` 関数の第2引数に比較対象の `Option` インスタンスを渡します。

```python
df_20230602 = cli.get_option_index_option("2023-06-02")
op_20230602 = Option(df_20230602)
jquants_derivatives.plot_volatility(op_20230605, op_20230602)
```

![op_20230602](./docs/images/op_20230602.png)