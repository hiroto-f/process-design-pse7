# CO2 Methanation Design Basis

このディレクトリは、Xu and Froment (1989) の Ni/MgAl2O4 触媒モデルを
使って CO2 メタネーション反応器を設計するための下準備です。

## 参照論文

- Jianguo Xu, Gilbert F. Froment,
  "Methane Steam Reforming, Methanation and Water-Gas Shift: 1. Intrinsic Kinetics",
  AIChE Journal, 35(1), 88-96, 1989.
- 元 PDF: `documents/Xu.pdf`

## Xu モデルで使う反応

論文の反応方向は次です。

```text
R1: CH4 + H2O <-> CO  + 3 H2
R2: CO  + H2O <-> CO2 + H2
R3: CH4 + 2 H2O <-> CO2 + 4 H2
```

CO2 メタネーションでは、主に `R3` と `R2` が逆向きに進みます。
実装では Xu 論文と同じ反応方向を保ち、負の反応速度で逆反応を表します。

## 作成したファイル

- `kinetics/xu_froment1989.py`
  - Table 5, Table 6 のパラメータ
  - Eq. (3) の速度式
  - 成分別生成速度の計算
- `thermo/equilibrium.py`
  - 反応 `R1-R3` の平衡定数
  - 速度式に必要な `K1`, `K2`, `K3`
- `data/xu_froment_1989_parameters.json`
  - 抽出値の機械可読な一覧
- `validation/validate_xu_parameters.py`
  - パラメータ計算と反応速度の簡易確認
- `reactor/staged_nonisothermal.py`
  - 3 段直列の非等温多管式固定床モデル
  - 段間冷却器で温度を指定値へ戻す計算
- `inputs/staged_reactor.json`
  - 現時点の設計前提を置いた入力例

## 論文から抽出した主要値

### 速度定数

`k_i = A_i exp(-E_i / RT)`

| Parameter | A | E [kJ/mol] |
| --- | ---: | ---: |
| `k1` | `4.225e15` | `240.1` |
| `k2` | `1.955e6` | `67.13` |
| `k3` | `1.020e15` | `243.9` |

### 吸着定数

`K_j = A_j exp(-DeltaH_j / RT)`

| Parameter | A | DeltaH [kJ/mol] |
| --- | ---: | ---: |
| `K_CO` | `8.23e-5` | `-70.65` |
| `K_H2` | `6.12e-9` | `-82.90` |
| `K_CH4` | `6.65e-4` | `-38.28` |
| `K_H2O` | `1.77e5` | `88.68` |

### 参照活性と fresh catalyst

- Table 5-6 の値は reference activity に対する値です。
- fresh catalyst で使う場合、論文 p.94 に従い反応速度定数 `k1-k3` を
  `2.246` 倍します。

## 適用上の注意

- Xu 論文のメタネーション側データは主に `573-673 K`、
  `H2/CO2 = 0.5-1.0` で取得されています。
- 現在の入力例は、確定している `H2 = 100 kg/h` を固定したうえで、
  `H2/CO2 = 4.0` となるよう `CO2 = 12.402 kmol/h` を置いています。
- 論文自身も、工業反応器設計では大粒径触媒の拡散抵抗を別途扱う必要があると
  明記しています。多管反応器の詳細設計では、有効係数または粒内拡散モデルを
  後段で追加してください。

## 3 段断熱モデル

実行:

```bash
./.venv/bin/python co2_methanation/run_staged_reactor.py
```

モデルでは次を仮定しています。

- 3 段直列
- 各段 100 本の代表管モデル
- 各段の管長 `0.2 m`
- 各段は断熱
- 入口温度と段間冷却後温度を独立に探索
- 探索温度は `573.15-673.15 K` を `10 K` 刻み
- 入口圧力 `10 bar`
- Xu 論文の reference activity

各段は断熱反応器として解きます。段間冷却器では、各段出口ガスを指定温度まで
戻して次段へ送ります。目的は、全段のガス温度が `300-400 C`
(`573.15-673.15 K`) に収まる入口温度と段間冷却温度の組み合わせを探すことです。

現在の入力は `H2/CO2 = 4.0` で、CO2 メタネーションの化学量論比に
合わせています。ただし、これは Xu 論文のメタネーション実験条件
`H2/CO2 = 0.5-1.0` の外側なので、速度式の外挿になります。

実行時には各温度ケースごとに次を出力します。

- `outputs/adiabatic_sweep/<ケース名>/summary.json`
- `outputs/adiabatic_sweep/<ケース名>/temperature_profile.png`
  - 3 段をつないだ管内ガス温度分布
- `outputs/adiabatic_sweep/<ケース名>/reaction_rate_profile.png`
  - `R1`, `R2`, `R3` の反応速度分布

全ケースの summary は `outputs/adiabatic_sweep/summary.json` にまとめて保存します。
温度条件を満たすケースだけは `outputs/adiabatic_sweep/feasible_cases.json`
にも保存します。

`summary.json` には次の性能指標も含めます。

- `overall_co2_conversion`
- `ch4_yield_on_co2_feed`
  - `CH4` 生成量 / `CO2` 供給量
- `ch4_selectivity_on_converted_co2`
  - `CH4` 生成量 / 消費 `CO2` 量
