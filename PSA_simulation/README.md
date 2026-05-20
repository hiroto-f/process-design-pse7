# PSA Simulation

Excel VBA マクロを、HYSYS を使わず実行するための Python 版です。

## フォルダ構成

```text
PSA_simulation/
├─ inputs/
│  ├─ common/
│  │  ├─ adsorbent.json
│  │  └─ components.json
│  └─ towers/
│     └─ tower_1.json
└─ outputs/
   └─ tower_1/
      ├─ summary.json
      ├─ adsorption_1_profile.csv
      ├─ desorption_profile.csv
      └─ adsorption_2_profile.csv
```

`inputs/common` には全塔で共通の物性値を置きます。`inputs/towers` には塔ごとの JSON を 1 ファイルずつ置きます。

## 実行

```powershell
python -m PSA_simulation.run_simulation
```

デフォルトでは以下を参照します。

- 共通入力: `PSA_simulation/inputs/common`
- 塔別入力: `PSA_simulation/inputs/towers`
- 出力: `PSA_simulation/outputs/<塔名>`

`tower_1` だけを実行する場合:

```powershell
python -m PSA_simulation.run_simulation --tower tower_1
```

この場合は `PSA_simulation/inputs/towers/tower_1.json` を使い、結果は `PSA_simulation/outputs/tower_1` に出力されます。

長い過渡計算を走らせず、物性値と塔設計のセットアップだけ確認する場合:

```powershell
python -m PSA_simulation.run_simulation --setup-only
```

## 入力JSON

共通 JSON:

- `adsorbent.json`
  - 吸着材の粒径、空隙率、孔半径、充填密度
- `components.json`
  - H2 と CH4 のラングミュアパラメータ、分子量、Lennard-Jones パラメータ

塔別 JSON:

- `tower_1.json`
  - `tower`: 圧力、温度、塔高/塔径、線速度
  - `feed`: 温度、圧力、体積流量、各成分の入口流量

入力値はセル位置ではなく、意味のあるキー名で管理します。

### `tower_1.json` の入力項目

`tower`:

| キー | 単位 | 内容 |
| --- | --- | --- |
| `adsorption_pressure_kpa` | kPa | 吸着時の塔圧力 |
| `desorption_pressure_kpa` | kPa | 脱着時の塔圧力 |
| `adsorption_temperature_c` | degC | 吸着温度。`feed.temperature_k` を省略した場合の温度計算にも使う |
| `height_to_diameter_ratio` | - | 塔高 / 塔径の比 |
| `adsorption_velocity_m_per_s` | m/s | 吸着時の線速度 |
| `adsorption_breakthrough_threshold` | - | 吸着終了しきい値。塔出口の規格化 `CH4` 濃度がこの値を超えると吸着終了 |
| `desorption_residual_loading_threshold` | - | 脱着終了しきい値。入口側の規格化 `CH4` 吸着量がこの値を下回ると脱着終了 |
| `purge_fraction` | - | パージ率。脱着時線速度は `吸着時線速度 x 吸着圧 / 脱着圧 x purge_fraction` で計算 |

`feed`:

| キー | 単位 | 内容 |
| --- | --- | --- |
| `temperature_k` | K | 供給ガス温度。省略時は `adsorption_temperature_c + 273.15` |
| `pressure_kpa` | kPa | 供給ガス圧力。省略時は `adsorption_pressure_kpa` |
| `volume_flow_m3_per_h` | m3/h | 供給ガスの体積流量。省略時は成分流量、温度、圧力から計算 |
| `components_kmol_per_h` | kmol/h | 成分ごとの入口モル流量 |

`components_kmol_per_h` の各要素:

| キー | 単位 | 内容 |
| --- | --- | --- |
| `name` | - | 成分名。`H2` と `CH4` は必須 |
| `flow_kmol_per_h` | kmol/h | その成分の入口モル流量 |

`H2` と `CH4` は PSA モデルで直接扱う 2 成分です。`other` のような追加成分も入口組成には含められますが、吸着計算では `H2` と `CH4` の流量を使って 2 成分組成を作ります。

## 出力

- `summary.json`
  - 塔寸法、供給条件、平均分子量、回収率、生成量、終了時間、CH4 濃縮指標などの要約
- `adsorption_1_profile.csv`
  - 1 回目吸着時の塔内分布
- `desorption_profile.csv`
  - 脱着時の塔内分布
- `adsorption_2_profile.csv`
  - 2 回目吸着時の塔内分布

`profile.csv` は `time_s, position_m, C_H2, C_CH4, q_H2, q_CH4, u` の列を持つ時系列データです。
