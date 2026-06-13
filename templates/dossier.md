---
id:                    # 例: gh#123 / bl-SHOP-45 / slack-1718 / local-xxx
source: local          # github | slack | backlog | local
source_ref:            # 元リンク（あれば）
title:
status: todo           # todo | in_progress | blocked | review | done
priority:              # high | mid | low
due:                   # YYYY-MM-DD（config の timezone 基準）
type:                  # bugfix | feature | research | review | docs | ops
project:               # 所属プロジェクト名
relates_to: []         # 例: [{id: "slack-1718", rel: same_as}]
sensitive: false       # true なら外部送信を抑止・同期除外
created:               # YYYY-MM-DD
updated:               # YYYY-MM-DD
---

# <title>

## 概要 / 背景

## 受け入れ条件 (Acceptance Criteria)
- [ ]

## 関連リンク・情報源

## 実装方針 / 手順（ワークフロー）
<!-- task-focus が種別テンプレ（templates/workflows/<type>.md）の手順をここに展開する -->

## 調査メモ
<!-- 出典つきで記録。確定知識は KB へ昇格 -->

## 決定事項 (Decisions)
<!-- 決めたこと＋根拠＋却下案 -->

## 進捗ログ (日付つき・末尾に追記。過去ログは消さない)

## 次アクション
<!-- 常に1つ。blocked のときは「何待ち＋解除条件」を書く -->
