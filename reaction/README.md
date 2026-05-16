# Methanation Reactor Model

`methanation_reactor.py` は、JSON 入力だけを使って非等温固定床反応器を計算します。
現在のサンプル入力 `inputs/input.json` は、主反応 1 本と副反応 2 本を
含む多管式反応器の反応ネットワークです。

初回セットアップ:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

```text
CO2 + 4 H2 -> CH4 + 2 H2O
CO2 + H2 -> CO + H2O
CO + 3 H2 -> CH4 + H2O
```

実行:

```bash
./.venv/bin/python -m reaction.methanation_reactor \
  --input reaction/inputs/input.json \
  --output reaction/outputs/summary.json \
  --profile-image reaction/outputs/temperature_profile.png \
  --rate-profile-image reaction/outputs/reaction_rate_profile.png
```

JSON には次を持たせています。

- `species`: 系内の全成分
- `reactions`: 各反応の式、化学量論係数、速度式
- `feed_kmol_per_h`: 入口流量
- `reactor`: 圧力、積分分割数、管本数
- `temperature_sweep_k`: 温度範囲
- `sizing`: 目標転化率、探索する最大触媒量
- `metrics`: 転化率と生成量を追跡する成分

各反応速度を個別に計算し、成分ごとの物質収支ではそれらを合算しています。
多管式として、全供給流量・全冷媒流量・触媒総量を管本数で等分し、
1 本の代表管を計算したうえで出口流量と除熱量を全管合計へ戻しています。
さらに `thermal` セクションで、一定 `Cp`、一定反応熱、一定 `UA` を持つ
向流冷却モデルを定義しています。冷媒は反応ガスと逆向きに流れるため、
ガス入口側の冷媒温度を未知数として、冷媒入口条件を満たすまで
シューティングで解いています。

温度範囲は 300-400 C 相当、すなわち約 573-673 K にしています。
`inputs/input.json` の各 `kinetics` や熱物性は、採用する触媒と設計温度域に
合わせて更新してください。計算結果の要約は
`outputs/summary.json` に保存されます。最高入口温度ケースの管内温度分布と
冷媒温度分布は `outputs/temperature_profile.png` に保存されます。
同じ代表管における各反応速度分布は `outputs/reaction_rate_profile.png`
に保存されます。
