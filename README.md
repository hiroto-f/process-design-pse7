# メタネーションのプロセス設計

> CO2 と H2 から CH4 をつくるメタネーションプロセスを、計算・設計・検証していくためのコード置き場。

![Status](https://img.shields.io/badge/status-prototype-1f6feb)
![Domain](https://img.shields.io/badge/domain-process%20design-2ea44f)
![Language](https://img.shields.io/badge/language-Python-3776ab)

## Overview

このリポジトリは、メタネーション反応を対象にしたプロセス設計用のコードを整理するための作業場です。
反応条件、物質収支、エネルギー収支、装置設計、シミュレーション結果を段階的に蓄積し、再現性のある設計検討につなげることを目指します。

## Scope

- 反応系の基礎計算
- 物質収支・エネルギー収支の整理
- プロセス条件の比較
- 計算スクリプトと検証メモの管理
- 将来的なシミュレーションモデルの拡張

## Repository

```text
.
├── README.md   # プロジェクト概要
└── test.py     # 初期スクリプト
```

## Quick Start

```bash
python test.py
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

- [ ] 物質収支計算の実装
- [ ] 反応熱・冷却負荷の計算
- [ ] 入力条件をまとめた設定ファイルの追加
- [ ] 結果出力フォーマットの整備
- [ ] 計算例と図表の追加

## License

未設定。
