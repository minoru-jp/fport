
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

### Removed

### Added


## [1.0.0] - 2025-08-19

### Changed
- policyの実装に`_Kernel`を導入
- `ProcessObserver`の実装をクラスインスタンスへ変更
- READMEの整備

### Removed

### Added
- テストを追加

## [0.3.0] - 2025-08-17

### Changed
- create_portで作るPortの実装をエラーが一度起こった後はlisten_funcを呼び出さないように修正。
- portの占有に関するガード節の順序を変更
- `Port.send()`を`message_validator`が出した例外を実装側に上げないように修正。
- 各モジュールのドキュメントを整備

### Removed

### Added

### Security
- Portの認証を双方向にして、SessionPolicy自身が作成したPortのみ接続を確立するように変更



## [0.2.0] - 2025-08-16

> 根本的な再設計を行いました。
> 大幅な改善点は、関数と関数ではなく、関数とPortをバインドする方法を取ったことによって、フレームスタックの取得の必要がなくなった点です。

### Changed
- `create_leak_policy`のスコープに関する引数を省略できないように変更。
- 引数は観察側と実装側のスコープを分けていたが、ベーススコープ一つを取るように変更。
- ベーススコープ以下であれば、実装側、観察側どちらをどこにおいてもよいという解釈に変更。
- `leak_port`の使用者(実装側)は観察側のスコープを明示的に制限できるという構成に変更。(指定しなければベースパスに準ずる)
- `Anchor.observed_target_function`から`CodeType`ではなくて関数そのものを返すように変更
- `Anchor` 各ゲッターをプロパティ化。
- `create_leak_policy`から3段階に分けて`deny`flagを設定できるようにした。いずれかのフラグが立つとAnchorは拒否される
- スコープ外からのアクセスの履歴を保持。
- `並列実行`と`再帰・再入・多態の解決`のどちらかを選ばなければならない、今のやり方だと両方は無理。`並列実行`を選ぶことにする。
- `get_anchor_verifier`に`verify`flagを設定。上位の`deny`に対して、ブロック単位での受け入れを表明できるようにするため。
- `leak_port`に`verify`フラグを設定。上位の`deny`に対して、実装個別の受け入れを表明できるようにするため。
- `create_leak_policy`に`absolute_deny`flagを設定。`verify`を無効化する。イタチごっこみたいだが、拒否に関してはLeakPolicyが一番の権限を持てる仕様とする。
- `_create_verified_anchor_unit`を`anchor.py`へ移行。これに際して`create_verified_anchor_unit`にリネーム。
- `session.py`を作成。`policy.py`から`Session`に関連するインターフェースと実装を移行、また`_create_session_full`を`create_session_full`にリネーム。
- `Leakage`を`PortDispatcher`にリネーム。これに関連して`LeakPort.get_anchor_verifier`を`.get_port_dispatcher`にリネーム。
- `LeakPort`を`LeakImplementation`にリネーム。これに関連して`LeakPolicy.get_leak_port`を`.get_leak_implementation`にリネーム。
- `ObservationPort`を`Standman`にリネーム。これに関連して`LeakPolicy.get_observation_port`を`.get_standman`にリネーム。
- `Anchor`を`Port`にリネーム。-> R
- Rに関連して`VerifiedAnchor`を`VerifiedPort`に、`UnverifiedAnchor`を`UnverifiedPort`に変更。
- Rに関連して`create_verified_anchor_unit`を`create_verified_port_unit`に変更。
- Rに関連して`Session.get_anchor`を`.get_port`に、`.get_noop_anchor`を`.get_noop_port`に変更。
- `Anchor.observe`を`.leak`に変更。
- `LeakPolicy.get_standman`を`.session_entry`にリネーム。元の`Standman.sessionn_entry`の機能をこちらで受け持つ。
- `Standman`をリークを受ける側のインターフェースとして再定義 ->D し、`standman.py`へ移動。
- `anchor.py`を`port.py`へ変更。
- `observer`というロールを`listener`に置き換え。これに関連した内部変数やシグネチャの変更。
- `create_verified_port_unit`のシグネチャを変更。リスナーとリスンファンクションを別々に受け取っていたのでリスナーのみ受け取るようにした。さらにリスナーを`ProcessObserver`から`Standman`に変更。
- `create_session_full`のシグネチャを変更。リスナーへの依存がなくなったため仮引数`observer`(現`listener`)を削除。
- `Port.process_observer`を`.listener`に変更。
- `Port.observed_target_function`を`.listened_function`に変更。
- `observer.py`を`process_observer/`へ移動しパッケージ分割。
- `Standman`を`Listener`にリネーム。
- `standman.py`を`listener.py`にリネーム。
- `create_leak_policy`のシグネチャに`tag_maxlen`と`bad_chars`を追加。`Port.leak`の実装は引数tagをチェックして、不正なら例外を投げることを仕様とする。
- `create_leak_policy`のシグネチャに`bad_words`を追加。そして`bad_chars`を取り消し。文字と単語の境を無くし、すべて単語として処理する。
- `Port.leak`を`.send`にリネーム。
- `LeakImplementation`の削除に伴い。`.get_port_dispatcher`を`LeakPolicy`に移行。
- `LeakPolicy`を`SessionPolicy`にリネーム。これに関連して`create_leak_policy`を`create_session_policy`にリネーム。
- `SessionFull.get_invocation_identifier`を`.get_session_id`にリネーム。
- `create_session_policy`のシグネチャの`bad_words`,`tag_maxlen`を取り消し。
- `create_session_policy`のシグネチャに`tag_validator`と`args_validator`を追加。これで、管理側にportに与えられたtagと引数をチェックするハンドラを受け取る。
- `Port.leak_policy`を`.session_policy`にリネーム。
- 概念的にセッションが送信側の関数(SF)を占有することにする。つまりセッション中、たとえどこからSFが呼ばれても、そのセッションのポートにマップされる仕様にする。
- 送信側のモジュール(`SessionPolicy.get_port_dispatcher()`を呼び出したモジュール)に暗黙的なマップを定義する。M
- 一つのポリシーが送信側モジュールを占有し、複数のポリシーがマップを定義しすることはできないものとする(共通のマップ名と、ロックを使用する)。
- `get_port_dispatcher`が定義していたlimited_scopeを廃止。どこで評価したらいいかわからなくなったので一旦廃止。
- 識別方法を次のように定義。管理側->モジュール名->送信側のディスパッチャー。送信側->送信関数の`CodeType`->受信側の`Session`。
- 根本的に再設計。



### Removed
- `Anchor.observer_scope_path` base_scopeに統合の為削除。
- `Anchor.observed_target_scope_path` base_scopeに統合の為削除。
- `NOOP_ANCHOR` を削除。情報をもったno-op Anchorをポリシー内で作成する方針に変更したため。
- `NOOP_ANCHOR_TARGET_FUNCTION_CODE`を削除。同上。
- `Anchor.souce_module_path`を削除。observe関数の場所を返していたが`ProcessObserver`そのものを返すようにしたため。
- `Anchor.enble_burst`を削除。やはり観察側の例外を実装側に流すのはおかしい。観察側の例外は観察側で処理、実装側は信頼できないスコープを使用しない。
- `ObserverPort`を削除。削除前に`Standman`へリネームされたが、リネーム後に削除。
- `LeakPolicy.get_observer_port`を削除。
- `Standman.session_entry`を削除。`LeakPolicy.session_entry`へ実装を移行。
- `ProcessObserver.set_observe_handler`を削除。
- `LeakImplementation`を削除。これに関連して`LeakPolicy.get_leak_implementation`を削除。
- `Session.get_invocation_identifier`を削除。
- 根本的に再設計。

### Added
- `Anchor.base_scope`　ベースパスを実装側へ提供する。
- `Anchor.process_observer` 紐づいている`ProcessObserver`を返す
- `Anchor.leak_policy` Anchorを作成した`LeakPolicy`を返す
- `VerifiedAnchor` 認証済みAnchorを表すマーカークラス
- `UnverifiedAnchor` 認証失敗時に返されるAnchorのマーカークラス
- `LeakPolicy.get_rejected_paths` スコープ外からのアクセスの履歴を返す。
- `standman.py`を追加。
- Dについて`Standman`を追加
- Dについて`Standman.leak`を追加
- `SessionState`を追加。これに関連して、`SessionFull.state`をプロパティとして追加。
- 上に関連して`SessionFull.verified`,`SessionFull.closed`を追加。
- `_SessionMap`を追加。これに関連して`_create_session_map`を追加。
- Mに関連して、`lockman.py`を追加。
- `lockman.get_global_slock`を追加。とりあえず一番広範囲なグローバルロックのみ提供する。
- 根本的に再設計。


## [0.1.0] - 2025-07-30

### Added
- 初期バージョンとして anchor / observer / policy / caller モジュールを実装。


