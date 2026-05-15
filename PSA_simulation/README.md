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

## 出力

- `summary.json`
  - 塔寸法、供給条件、平均分子量、回収率、生成量、終了時間などの要約
- `adsorption_1_profile.csv`
  - 1 回目吸着時の塔内分布
- `desorption_profile.csv`
  - 脱着時の塔内分布
- `adsorption_2_profile.csv`
  - 2 回目吸着時の塔内分布

`profile.csv` は `time_s, position_m, C_H2, C_CH4, q_H2, q_CH4, u` の列を持つ時系列データです。

## Excel からCSVを出力する場合

```powershell
python -m PSA_simulation.export_workbook_csv "C:\path\to\workbook.xlsm" --output-dir PSA_simulation\csv_input_export
```

このエクスポート機能は、旧 Excel シートの確認用です。現在の標準入力は `inputs/**/*.json` です。
