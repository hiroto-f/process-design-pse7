# Champon Methanation Reactor Model

`champon_reactor.py` は、Champon et al. (2019) の CO2 メタネーション速度式を
使う JSON 駆動の非等温多管式固定床反応器モデルです。

反応ネットワーク:

```text
CO2 + 4 H2 -> CH4 + 2 H2O
CO2 + H2 -> CO + H2O
CO + 3 H2 -> CH4 + H2O
```

Champon モデルは次を同時に扱います。

- 直接経路: `CO2 methanation`
- 間接経路: `reverse water-gas shift` + `CO methanation`

実行:

```bash
./.venv/bin/python -m reaction_Champon.champon_reactor \
  --input reaction_Champon/inputs/input.json \
  --output reaction_Champon/outputs/summary.json \
  --profile-image reaction_Champon/outputs/temperature_profile.png \
  --rate-profile-image reaction_Champon/outputs/reaction_rate_profile.png \
  --position-profile-image reaction_Champon/outputs/temperature_profile_z.png \
  --position-rate-profile-image reaction_Champon/outputs/reaction_rate_profile_z.png
```

`inputs/input.json` では次を設定できます。

- `kinetics.kinetic_constants`: Champon Table 3 の `k0` と `Ea`
- `kinetics.adsorption_constants`: Champon Table 3 の `K0` と `Q`
- `reactor.tube_count`: 管本数
- `reactor.tube_inner_diameter_m`: 管内径
- `reactor.tube_length_m`: 管長
- `reactor.catalyst_bulk_density_kg_per_m3`: `W` から `z` への換算に使う充填触媒密度
- `temperature_sweep_k`: 入口温度範囲
- `thermal.countercurrent_cooling`: 向流冷却条件

サンプル入力の `UA` は、冷媒温度分布が反応器挙動へ実際に効くようにした
設計用の仮定値です。実機設計では伝熱面積、総括伝熱係数、管寸法から
再同定してください。

現在のサンプルでは、Champon モデルの適用範囲 `623-723 K` から外れないように、
冷媒入口温度を `624 K`、`UA` を `7500 kJ/(kgcat h K)` に設定しています。

現在の入力は、Champon 論文の適用範囲 `623-723 K` のうち、
もともとの設計条件と重なる `623-673 K` を使っています。
`300 C` 相当の `573 K` は Champon 論文の検証範囲外なので、このモデルでは
入力チェックで除外しています。

生成物:

- `outputs/summary.json`: 各入口温度での反応結果
- `outputs/temperature_profile.png`: 代表管のガス温度と冷媒温度
- `outputs/reaction_rate_profile.png`: 代表管の各反応速度分布
- `outputs/temperature_profile_z.png`: `z` 軸で見た代表管のガス温度と冷媒温度
- `outputs/reaction_rate_profile_z.png`: `z` 軸で見た代表管の各反応速度分布

`Champon et al. (2019)` の本文には、`W` から `z` への換算に必要な
充填触媒密度は明示されていないため、サンプル入力では別途仮定値を与えています。
現在のサンプルでは、管内径 `20 mm`、管長 `2 m`、管本数 `100` 本、
充填触媒密度 `800 kg/m3` とし、幾何から決まる総触媒量 `50.265 kg` を
利用可能触媒量として使っています。画像はこの `2 m` の全長プロファイルです。
