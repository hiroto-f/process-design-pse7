# メタネーションのプロセス設計

> CO2 と H2 から CH4 をつくるメタネーションプロセスを、HYSYS と Python で設計・検証していくためのコード置き場。

![Status](https://img.shields.io/badge/status-prototype-1f6feb)
![Domain](https://img.shields.io/badge/domain-process%20design-2ea44f)
![Language](https://img.shields.io/badge/language-Python-3776ab)
![Tool](https://img.shields.io/badge/tool-Aspen%20HYSYS-005eb8)

## Overview

このリポジトリは、メタネーション反応を対象にした 1 つの HYSYS テンプレートを Python から操作し、反応条件・物質収支・エネルギー収支・装置構成を段階的に検討するための作業場です。

`methanation.tpl` を育てていく前提で、成分リストや物性パッケージなどのテンプレート準備作業をスクリプト化しています。

## Repository

```text
.
├── README.md
├── .gitignore
├── connect_test/
│   ├── check_rot.py                  # HYSYS の ROT 登録確認
│   └── test.py                       # HYSYS COM 接続テスト
└── hysys_methanation/
    ├── __init__.py
    ├── complete_components.py        # methanation.tpl の成分リスト補完
    ├── create_property_package.py    # Peng-Robinson 物性パッケージ作成
    └── create_reactions.py           # メタネーション反応セット作成
```

## Requirements

- Windows
- Python
- `pywin32`
- Aspen HYSYS V14.0
- HYSYS が通常権限で起動し、モーダルダイアログが閉じられていること

`pywin32` がない場合:

```powershell
pip install pywin32
```

## Connection Check

HYSYS を起動した状態で、まず COM 接続を確認します。

```powershell
python connect_test\test.py
```

成功例:

```text
[HYSYS TEST] CONNECTED
Version: Aspen HYSYS Version 14 (40.0)
Open simulation cases: 2
```

接続が不安定な場合は、ROT 登録を確認します。

```powershell
python connect_test\check_rot.py
```

## Complete Components

`methanation.tpl` を HYSYS 経由で開き、メタネーション計算に必要な成分を Component List に追加します。

追加対象:

- Hydrogen
- Carbon Dioxide
- Methane
- Water
- Carbon Monoxide

指定した `methanation.tpl` を直接更新します。

```powershell
python -m hysys_methanation.complete_components --template "C:\Users\Fukada Hiroto\Documents\プロセス設計\hysisファイル\methanation.tpl"
```

## Create Property Package

`methanation.tpl` を HYSYS 経由で開き、Fluid Package を作成して `Methanation Components` という Component List を割り当てます。見つからない場合は、テンプレート内の先頭の Component List を使います。
指定した `methanation.tpl` を直接更新します。

```powershell
python -m hysys_methanation.create_property_package --template "C:\Users\Fukada Hiroto\Documents\プロセス設計\hysisファイル\methanation.tpl"
```

物性パッケージの種類は HYSYS の GUI で選択します。スクリプト実行後、HYSYS の `物性パッケージ` 画面で対象行を開き、物性パッケージとして `Peng-Robinson` を選択してください。ステータスが「必要な入力が完了していません」のままの場合は、`成分リスト` が `Methanation Components` になっていることと、物性パッケージ欄に `Peng-Robinson` が入っていることを確認してから保存します。

## Create Reactions

`methanation.tpl` を HYSYS 経由で開き、メタネーション用の Reaction Set を作成します。

PDF 資料の Xu & Froment のグローバル反応系をもとに、テンプレートには次の反応を登録します。

- CO2 Methanation: `CO2 + 4H2 -> CH4 + 2H2O`
- Reverse Water-Gas Shift: `CO2 + H2 -> CO + H2O`
- CO Methanation: `CO + 3H2 -> CH4 + H2O`

HYSYS V14 の COM では反応オブジェクトの新規作成が安定しないため、反応の作成は HYSYS の GUI で行います。HYSYS の `反応` 画面で `不均一系触媒` を選び、空の反応を 3 つ作成して、名前を `CO2 Methanation`、`Reverse Water-Gas Shift`、`CO Methanation` にしてください。スクリプトは既存の不均一系触媒反応を探し、成分、化学量論係数、Xu & Froment ベースの速度式パラメータを設定します。

速度式は HYSYS の Langmuir-Hinshelwood 形式に合わせ、Xu & Froment の元反応方向を逆向きにして入力します。HYSYS に登録している反応は Xu & Froment の逆方向なので、HYSYS の正反応定数は `k_i / K_i`、逆反応定数は `k_i` とします。

```text
r = (kf * product(p_i^nf_i) - kr * product(p_i^nr_i)) / DEN^2
DEN = 1 + KCO*pCO + KH2*pH2 + KCH4*pCH4 + KH2O*pH2O/pH2
K_i = Aeq_i * exp(-C_i / T)
E_forward = E_i - R*C_i
```

使用する平衡定数は、`T [K]`、`R = 8.314 kJ/(kgmole K)` として以下です。

| Xu & Froment 反応 | 平衡定数 |
|---|---|
| I: `CH4 + H2O <-> CO + 3H2` | `K1 = 1.198e17 * exp(-26830 / T)` |
| II: `CO + H2O <-> CO2 + H2` | `K2 = 1.767e-2 * exp(4400 / T)` |
| III: `CH4 + 2H2O <-> CO2 + 4H2` | `K3 = 2.117e15 * exp(-22430 / T)` |

HYSYS に入力する速度パラメータは以下です。`E` の単位は HYSYS 表示に合わせて `kJ/kgmole` です。

| HYSYS 反応 | 正反応 A | 正反応 E | 正反応次数 | 逆反応 A | 逆反応 E | 逆反応次数 |
|---|---:|---:|---|---:|---:|---|
| CO2 Methanation | `4.8181389e-1` | `57406.6` | `CO2:1, H2:0.5` | `1.020e15` | `243900` | `CH4:1, H2O:2, H2:-3.5` |
| Reverse Water-Gas Shift | `1.1063950e8` | `103713.6` | `CO2:1` | `1.955e6` | `67130` | `CO:1, H2O:1, H2:-1` |
| CO Methanation | `3.5267112e-2` | `17023.0` | `CO:1, H2:0.5` | `4.225e15` | `240100` | `CH4:1, H2O:1, H2:-2.5` |

分母項のパラメータは全反応で共通です。

| 分母項 | A | E | 成分次数 |
|---|---:|---:|---|
| `KCO*pCO` | `8.23e-5` | `-70650` | `CO:1` |
| `KH2*pH2` | `6.12e-9` | `-82900` | `H2:1` |
| `KCH4*pCH4` | `6.65e-4` | `-38280` | `CH4:1` |
| `KH2O*pH2O/pH2` | `1.77e5` | `88680` | `H2O:1, H2:-1` |

```powershell
python -m hysys_methanation.create_reactions --template "C:\Users\Fukada Hiroto\Documents\プロセス設計\hysisファイル\methanation.tpl"
```

分母指数は手動で２に設定してください。

## Design Notes

メタネーションの代表反応:

```text
CO2 + 4H2 -> CH4 + 2H2O
```

主に以下の観点から設計を進めます。

- 原料比と転化率
- 反応熱と温度制御
- 生成物中の水分除去
- 未反応ガスのリサイクル
- 装置構成と運転条件

## Roadmap

- [x] HYSYS COM 接続テスト
- [x] 成分リスト補完スクリプト
- [x] Peng-Robinson 物性パッケージ作成スクリプト
- [x] メタネーション反応セット作成スクリプト
- [ ] 物質収支計算の実装
- [ ] ストリーム条件の読み取り・書き込み
- [ ] 反応器条件の自動設定
- [ ] 計算結果の CSV 出力
