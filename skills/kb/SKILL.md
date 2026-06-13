---
name: kb
description: プロジェクトや汎用の知識をナレッジベース（~/.hiyokb/kb・projects/<名>/kb）に追記・検索・昇格する。「これKBに残して」「〜について知ってること」「ナレッジ化して」「過去の知見を調べて」などのときに使う。知識どうしをリンクで結び、横断的に引けるようにする。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# kb — ナレッジベースの追記・検索・昇格

知識は「貯める」だけでなく「**結ぶ**」。新情報は必ず既存ページとリンクで繋ぐ。運用規約は対象 KB の `SCHEMA.md` に従う。

## モード判定（$ARGUMENTS と文脈から）
- **検索/質問**: 既存知識を引く → 「検索」へ
- **追記/ナレッジ化**: 新しい知識を残す → 「追記」へ
- **昇格**: inbox の素材を確定知識にする → 「昇格」へ

## 検索（グラフ走査）
1. 該当 KB の `index.md`（内容カタログ）をまず読む。
2. 関連ページを Grep/Read し、**`[[ ]]` リンクを辿って近傍ページも読む**（孤立した断片でなく文脈ごと把握）。
3. **出典付きで合成回答**。価値ある回答は新規ページ化して KB に還元してよい（その場合は「追記」へ）。

## 追記（新規ページ or 既存改訂）
1. 行き先を決める: 横断汎用＝`~/.hiyokb/kb/`、特定プロジェクト＝`projects/<名>/kb/`。
2. 新規は `${CLAUDE_PLUGIN_ROOT}/templates/kb-article.md` を雛形に作成。`title/summary/tags/source/updated` を埋める。**`source`（出自）は必須**。
3. **リンクを必ず結ぶ（中核）**:
   - 本文で関連トピックを `[[トピック名]]` で参照。
   - 関係に型があれば frontmatter `relates_to: [{page, rel}]`（rel: relates_to/depends_on/extends/supersedes/contradicts/source_of）。
   - **双方向**を意識（相手ページからもこのページへ繋ぐ）。後で `kb-lint --fix` が片方向を補完する。
4. 索引を決定論的に再生成:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_kb_index.py"
   ```
5. `~/.hiyokb/log.md` に追記される（lint/index 実行時）。大きな追記は一言サマリを残してもよい。

## 昇格（inbox → KB / 昇格ゲート）
- inbox の素材のうち、**出所が明確で確定した知識だけ**を KB ページ化する。
- 未確定・噂・要約途中は昇格しない（inbox に留める）。`config.yaml` の `promotion.auto` が `always_confirm` なら人に確認。
- 昇格したら出自（元 inbox ファイル/日付）をページの `source` に明記。

## 機密
- `sensitive` な内容は外部送信を避け、必要なら別管理。

## 原則
- index.md は自動生成物。手編集しない。
- 孤立ページを作らない（必ずどこかと結ぶ）。健全性は `/hiyokb:kb-lint` で点検。
