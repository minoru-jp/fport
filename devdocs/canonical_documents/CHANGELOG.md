<!--
この文書は `shikumi-devdoc` によって生成された canonical document です。
Canonical source は `devdocs/canonical_sources/changelog/canonical.py` です。
直接編集しないでください。

公開文書作成方針

- `devdocs/canonical_documents/` にある日本語 canonical document を公開工程の入力とする。
- 翻訳では意味、構造、情報量を維持し、内容を勝手に追加・削除・要約しない。
- canonical document に `shikumi-devdoc:translation-metadata` が含まれる場合は、その `preserve_spelling` 指定の用語の表記を変更しない。
- コード、Python 識別子、コマンド、ファイルパス、URL は、翻訳上の必要がない限り変更しない。
- このコメントブロックは published document には含めない。
- published document は canonical document から派生する公開成果物として扱い、内容の変更が必要な場合は canonical source または realization context へ戻して canonical document を再生成する。
-->

# fport 変更履歴

`fport` の版ごとの変更を記録する。`2.0.0` より前の版(`1.x` 系)は作り直す前の旧実装で、その履歴はこの文書に含めない。

## V2_0_0

**設計から作り直した版であり、`1.x` 系との後方互換性はまったくない。** `1.x` の API はどれも残っておらず、移行の手段も用意しない。

`1.x` は、送信口への接続を守るための認証(ポリシーによる `Port` の生成と照合)、接続の拒否の設定、セッションの状態の受け渡し、条件を監視する Observer までを抱えて大きくなりすぎた。この版では、`1.x` の芯だった「実装側に置いた送信口が、実装側の振る舞いを変えない」という考え方だけを残した。同じプロセスの中での認証は守りにならないので扱わず、受け取った情報の運び方やリスナーの失敗の扱いは受信側(必要なら gpframe)に任せた。

version: 2.0.0

released on: 2026-10-10

Changed:

- 対象の Python バージョン範囲を `>=3.10` から `>=3.11` に変更した。
- `Port` を、ポリシーを介さずに `fport.Port()` で直接作るように変更した。
- リスナーの接続を、`SessionPolicy.session()` のセッションから、`Port.connect()` が返す `Connection` に変更した。`Connection` は `with` 文で使え、`disconnect()` で外せる。
- リスナーが失敗した後も、`send()` のたびにリスナーを呼び続けるように変更した。`1.x` は最初の失敗の後、セッションが終わるまでリスナーを呼ばなかった。失敗した後に止めるかどうかは受信側が決める。

Added:

- リスナーの失敗を受信側に渡すエラーハンドラ(`Port.connect()` の `on_error`)を追加した。
- 接続の状態を見る `Port.connected` と `Connection.active` を追加した。
- gpframe のフレーム用ルーティン `fport.gpframe.tap` を追加した。`Port` に届いたものを `Channel` へ流し続け、停止の要求で接続を外して戻り、リスナーの失敗をフレームの失敗として送出する。どの終わり方でも `Channel` を閉じる。fport は gpframe に依存しない。
- 振る舞いの約束を `shikumi-contrace` の契約として `contract/` に置き、すべての条項をテストに結びつけた。
- PEP 561 の `py.typed` を追加した。
- 作例を `examples/` に追加した。テストで内部の判断を観察する `lru_cache.py`、計測の差し込み口の `progress.py`、gpframe と組み合わせる `pipeline_monitor.py` の 3 つである。

Removed:

- `create_session_policy()` と `SessionPolicy`(`create_port()`、`create_noop_port()`、`session()`)を削除した。
- `SessionPolicy` と `Port` の間の認証(`Port` を作ったポリシー以外からの接続の拒否)を削除した。
- 接続の拒否の設定(`block_port`、no-op の `Port`)と `DeniedError` を削除した。
- 送信前の検証関数 `message_validator` を削除した。
- `SessionState`(`ok`、`error`)を削除した。リスナーの失敗は `on_error` で受け取る。
- `SendFunction` と `ListenFunction` の Protocol を削除した。
- `fport.observer`(`ProcessObserver`、`Observation`、`ConditionStat`、`ExceptionKind`)を削除した。

Fixed:

- `with` 文の中で例外が起きると、`Port` が占有されたまま残り、次の接続が `OccupiedError` になっていた問題を修正した。`Connection` は例外で抜けた場合も接続を外す。
- リスナーが投げた `KeyboardInterrupt` などの `BaseException` を `send()` が握りつぶし、中断が効かなくなっていた問題を修正した。`Exception` ではない `BaseException` は送信側へそのまま伝わる。
