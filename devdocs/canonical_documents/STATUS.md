<!--
この文書は `shikumi-devdoc` によって生成された canonical document です。
Canonical source は `devdocs/canonical_sources/status/canonical.py` です。
直接編集しないでください。

公開文書作成方針

- `devdocs/canonical_documents/` にある日本語 canonical document を公開工程の入力とする。
- 翻訳では意味、構造、情報量を維持し、内容を勝手に追加・削除・要約しない。
- canonical document に `shikumi-devdoc:translation-metadata` が含まれる場合は、その `preserve_spelling` 指定の用語の表記を変更しない。
- コード、Python 識別子、コマンド、ファイルパス、URL は、翻訳上の必要がない限り変更しない。
- このコメントブロックは published document には含めない。
- published document は canonical document から派生する公開成果物として扱い、内容の変更が必要な場合は canonical source または realization context へ戻して canonical document を再生成する。
-->

# fport Project Status

`fport` の現在の状態と、現在から見た今後の方向を記述する。
過去に実際に起きた変更は CHANGELOG が担当する。

## STATUS_001

現在の開発段階は Alpha。現在のバージョンは `2.0.0` で、PyPI にはまだ公開していない。PyPI 上の最新は、作り直す前の旧実装 `1.0.3` である。

title: Development stage

## STATUS_002

対象の Python バージョン範囲は `>=3.11`。`fport.gpframe.tap` が、リスナーの複数の失敗を標準の `ExceptionGroup` でまとめるためである。実行時の依存パッケージはない。

title: Supported Python

## STATUS_003

提供している機能は次のとおり。

- 実装側に置く送信口 `Port` と、その `send()`。接続がなければ何もせず、送信側に `Exception` を伝えず、ロックを取らない
- リスナーの接続 `Port.connect()` と、接続 `Connection`(`disconnect()`、`with` 文)。接続できるリスナーは一つで、接続済みの `Port` への接続は `OccupiedError` になる
- リスナーの失敗を受信側に渡すエラーハンドラ(`connect()` の `on_error`)
- gpframe のフレーム用ルーティン `fport.gpframe.tap`。`Port` に届いたものを `Channel` へ流し、停止で終わり、リスナーの失敗をフレームの失敗にする

接続の認証や、送信先の制限は扱わない。同じプロセスの中のコードはすべて同じ信頼の範囲にあり、それを分けるのはプロセスや OS の境界の役目だからである。リスナーとのやり取りを状態として持つセッションも扱わない。接続の期間を管理したい場合は、`with` 文か、gpframe のフレームの寿命を使う。

title: Scope

## STATUS_004

fport には Specification 文書を置かず、`contract/` にある `shikumi-contrace` の契約を振る舞いの正本とする。公開 API の形は `contract/ports/surface.py` に Protocol として置いている。契約は `PortContract`、`ConnectionContract`、`TapContract` の 3 つである。

pytest で、契約のすべての条項に少なくとも一つのテストが結びついていることを確かめている。pytest は `--contrace-check` を常に付けて実行し、警告をすべてエラーとして扱う。

`TapContract` のテストは、gpframe の `Context` と `Channel` の振る舞いを真似た偽物で行う。gpframe そのものと組み合わせたテスト、README の gpframe の例、作例 `pipeline_monitor.py` のテストは、gpframe が入っている環境でだけ実行し、入っていなければ飛ばす。

title: Contracts and tests

## STATUS_005

すべての検査は `tools/check.py` にまとめている。`docs`(canonical document が最新で、英語の公開文書が canonical document と食い違っていない)、`format`、`lint`、`types`、`types-tests`、`tests`、`dist`(sdist と wheel を作り、`twine check --strict`、中身の検査、依存のないきれいな venv での動作確認、版がタグ・パッケージ・文書・CHANGELOG で揃っていることの確認)の 7 つで、`python tools/check.py` ですべて、名前を並べれば一部だけを実行する。これとは別に、リリースのときだけ明示して走らせる `published` がある。`docs` が通り、版が揃い、CHANGELOG のその版の項に公開日(`released_on`)があること、つまり文書がその版を公開した状態になっていることを確かめる。

検査に使う道具の版は `pyproject.toml` の extra で固定している(`ruff==0.17.0`、`basedpyright==1.40.2`、`shikumi-contrace==0.1.0`、`shikumi-devdoc==0.3.5`、`gpframe==0.1.0`、`build==1.6.1`、`twine==7.0.0`)。`dev` ですべてが入る。BasedPyright は `src`、`contract/ports`、`scripts`、`tools`、`examples` を `recommended` で、テスト・契約・文書の正本を利用側として `standard` で検査し、どちらも 0 errors / 0 warnings である。

title: Checks

## STATUS_009

GitHub Actions は 3 つのワークフローからなる。

- `checks.yml`: 再利用されるワークフローで、Python 3.11、3.12、3.13 で `python tools/check.py` を実行する。検査の中身は `tools/check.py` だけに置く。
- `ci.yml`: push とプルリクエストのたびに `checks.yml` を呼ぶ。
- `release.yml`: GitHub で Release を公開したときに、まず `checks.yml` を呼んで push 時と同じ検査を通す。続いて `python tools/check.py dist --tag <tag>` で配布物を作って確かめ(タグが `v<version>` と一致することも確かめる)、最後に `python tools/check.py published --tag <tag>` で文書が公開済みの状態になっていることを確かめてから、PyPI の Trusted Publishing で公開する。API トークンは使わない。

Trusted Publishing のために、PyPI 側でこのリポジトリ、ワークフロー `release.yml`、環境 `pypi` を Trusted Publisher として登録しておく必要がある。

リリースの前には、CHANGELOG のその版の項に `released_on` を入れ、STATUS と CHANGELOG の「まだ PyPI に公開していない」という記述を公開後の状態に改め、文書を生成し直して英語の公開文書を翻訳し直す。これを済ませないと `published` で止まり、PyPI には公開されない。

title: Checks, CI and release

## STATUS_007

gpframe は fport の実行時の依存ではない。ただし開発では、`fport.gpframe` を gpframe そのものと組み合わせて確かめるために使い、`test` extra で `gpframe==0.1.0` に固定している。

gpframe が入っていない環境では、gpframe を使うテスト(結合テスト、README の gpframe の例、作例 `pipeline_monitor.py`)は飛ばされ、残りのテストは通る。テストの型検査(`types-tests`)は gpframe の型を参照するので、gpframe が必要である。

title: gpframe in development

## STATUS_008

`examples/` に、送信口の使い道ごとの作例を 3 つ置いている。テストで内部の判断を観察する `lru_cache.py`、計測の差し込み口の `progress.py`、gpframe と組み合わせる `pipeline_monitor.py` である。`tests/test_examples.py` が、どれも書いてあるとおりに動くことを確かめる。

`pipeline_monitor.py` では、監視の側が想定していないものを受け取ったとき、Monitor のフレームが接続を外すまでの間に、ワーカーから届いた分の失敗が集まることを確かめた。1 件ならその例外、複数なら `ExceptionGroup` として送出され、どちらの場合もワーカーには何も起きない。これは `TapContract` のとおりの振る舞いである。

拡張の入口(プラグインのフックなど)の作例は置いていない。送信口は一方向で戻り値を返さないので、動作を変えるフックを期待させてしまうからである。

title: Examples

## STATUS_006

文書は README、Project Status、CHANGELOG の 3 つで、`devdocs/canonical_sources/` の日本語の正本から `shikumi-devdoc` で `devdocs/canonical_documents/` に生成する。生成は `python scripts/render_devdocs.py` で行う。

英語の公開文書は、日本語の canonical document を翻訳してリポジトリのルートに置き、パッケージの README にはルートの `README.md` を使う。翻訳そのものは自動化していない。`scripts/published_docs.py` が次を機械で確かめる(`tools/check.py docs` に含まれる)。

- すべての canonical document に公開文書がある
- 公開文書の先頭の印が、いまの canonical document の SHA-256 と一致する。canonical document が変わると、翻訳し直して `python scripts/published_docs.py stamp <公開文書>` で印を付け直すまで失敗する
- Python のコード例が、コメントと docstring を除いて canonical document と同じである
- 識別子の見出し(`STATUS_001` など)が、同じ順に同じだけある
- リンクの先が実在する

title: Documents
