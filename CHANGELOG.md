
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- Template for reference -->
<!--
### Added
- 新機能や追加された API

### Changed
- 既存の動作・インターフェースの変更（非互換含む）

### Deprecated
- 廃止予定になった機能や API

### Removed
- 完全に削除された機能やコード

### Fixed
- バグ修正や明示的な不具合対応

### Security
- セキュリティ向上や脆弱性修正
-->

## [Unreleased]

### Changed
- `create_leak_policy`のスコープに関する引数を省略できないように変更。
- 引数は観察側と実装側のスコープを分けていたが、ベーススコープ一つを取るように変更。
- ベーススコープ以下であれば、実装側、観察側どちらをどこにおいてもよいという解釈に変更。
- `leak_port`の使用者(実装側)は観察側のスコープを明示的に制限できるという構成に変更。(指定しなければベースパスに準ずる)
- `Anchor.observed_target_function`から`CodeType`ではなくて関数そのものを返すように変更
- `Anchor` 各ゲッターをプロパティ化。
- `create_leak_policy`から3段階に分けて`deny`flagを設定できるようにした。いずれかのフラグが立つとAnchorは拒否される
- スコープ外からのアクセスの履歴を保持。
- `並列実行`と`再帰・再入・多態の解決`のどちらかを選ばなければならない、両方は無理。`並列実行`を選ぶことにする。

### Removed
- `Anchor.observer_scope_path` base_scopeに統合の為削除。
- `Anchor.observed_target_scope_path` base_scopeに統合の為削除。
- `NOOP_ANCHOR` を削除。情報をもったno-op Anchorをポリシー内で作成する方針に変更したため
- `NOOP_ANCHOR_TARGET_FUNCTION_CODE`を削除。同上。
- `Anchor.souce_module_path`を削除。observe関数の場所を返していたが`ProcessObserver`そのものを返すようにしたため。
- `Anchor.enble_burst`を削除。やはり観察側の例外を実装側に流すのはおかしい。観察側の例外は観察側で処理、実装側は信頼できないスコープを使用しない。

### Added
- `Anchor.base_scope`　ベースパスを実装側へ提供する。
- `Anchor.process_observer` 紐づいている`ProcessObserver`を返す
- `Anchor.leak_policy` Anchorを作成した`LeakPolicy`を返す
- `VerifiedAnchor` 認証済みAnchorを表すマーカークラス
- `UnverifiedAnchor` 認証失敗時に返されるAnchorのマーカークラス
- `LeakPolicy.get_rejected_paths` スコープ外からのアクセスの履歴を返す。

## [0.1.0] - 2025-07-30

### Added
- 初期バージョンとして anchor / observer / policy / caller モジュールを実装。