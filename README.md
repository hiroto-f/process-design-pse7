# メタネーションのプロセス設計

> CO2 と H2 から CH4 をつくるメタネーションプロセスを、HYSYS と Python で設計・検証していくためのコード置き場。

![Status](https://img.shields.io/badge/status-prototype-1f6feb)
![Domain](https://img.shields.io/badge/domain-process%20design-2ea44f)
![Language](https://img.shields.io/badge/language-Python-3776ab)
![Tool](https://img.shields.io/badge/tool-Aspen%20HYSYS-005eb8)

## Overview

このリポジトリは、メタネーション反応を対象にした HYSYS テンプレートを Python から操作し、反応条件・物質収支・エネルギー収支・装置構成を段階的に検討するための作業場です。

最初の自動化として、`methanation.tpl` の成分リストを Python から補完するスクリプトを用意しています。

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
    └── complete_components.py        # methanation.tpl の成分リスト補完
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

既定では元のテンプレートを上書きせず、同じフォルダに `methanation_components.tpl` として保存します。

```powershell
python -m hysys_methanation.complete_components --template "C:\Users\Fukada Hiroto\Documents\プロセス設計\hysisファイル\methanation.tpl"
```

保存先を指定する場合:

```powershell
python -m hysys_methanation.complete_components --template "C:\Users\Fukada Hiroto\Documents\プロセス設計\hysisファイル\methanation.tpl" --output "C:\Users\Fukada Hiroto\Documents\プロセス設計\hysisファイル\methanation_ready.tpl"
```

元の `methanation.tpl` を直接更新する場合:

```powershell
python -m hysys_methanation.complete_components --template "C:\Users\Fukada Hiroto\Documents\プロセス設計\hysisファイル\methanation.tpl" --in-place
```

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
- [ ] 物質収支計算の実装
- [ ] ストリーム条件の読み取り・書き込み
- [ ] 反応器条件の自動設定
- [ ] 計算結果の CSV 出力
