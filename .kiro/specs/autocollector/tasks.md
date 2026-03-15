# AutoCollector タスク

## Task 1: プロジェクト基盤セットアップ
- [ ] pyproject.toml 作成（プロジェクトメタデータ、依存関係、エントリポイント）
- [ ] src/mikage_collector/__init__.py 作成
- [ ] パッケージ構成（scanner/, mcp/, definitions/builtin/）のディレクトリ・__init__.py作成
- [ ] Dockerfile 作成

## Task 2: 定義ファイルローダー (scanner/definition.py)
- [ ] Pydanticモデル定義（StepDefinition, ResourceDefinition, ServiceDefinition）
- [ ] YAMLファイル読み込み + バリデーション
- [ ] ビルトインディレクトリ（パッケージ同梱）からの定義読み込み
- [ ] カスタムディレクトリからの定義読み込み
- [ ] 不正な定義のスキップ + ログ出力

## Task 3: API実行エンジン (scanner/executor.py)
- [ ] boto3クライアント生成（リージョン、プロファイル、AssumeRole対応）
- [ ] 単一ステップのAPI実行（action → result_key抽出）
- [ ] ページネーション自動処理（can_paginate判定 → paginator使用）
- [ ] $変数参照の解決（前ステップ結果 → 次ステップパラメータ注入）
- [ ] for_each イテレーション処理
- [ ] JMESPath式によるネスト配列からのフィールド抽出
- [ ] エラーハンドリング（AccessDenied スキップ、Throttling リトライ）

## Task 4: スキャンエンジン (scanner/engine.py)
- [ ] 定義ファイル群の依存順ソート（depends_on解決）
- [ ] リージョンごとのスキャン実行ループ
- [ ] 結果のJSON構造組み立て（設計書の出力フォーマット準拠）
- [ ] summary生成（total_resources, by_service, definitions_used, errors）

## Task 5: CLIエントリポイント (cli.py)
- [ ] click ベースのCLI構成（scan / serve サブコマンド）
- [ ] scan サブコマンド: --region, --service, --definitions, --definition-file, --role-arn, --profile, --output
- [ ] JSON出力（stdout / ファイル）
- [ ] ログ出力設定（--verbose / --quiet）

## Task 6: ビルトイン定義ファイル作成
- [ ] ec2.yaml（instances, vpcs, subnets, security_groups）
- [ ] rds.yaml（db_instances, db_clusters）
- [ ] ecs.yaml（clusters, services）※ list→describe パターン
- [ ] lambda.yaml（functions）
- [ ] elbv2.yaml（load_balancers, target_groups）
- [ ] s3.yaml（buckets）※ グローバルサービス

## Task 7: MCP Server (mcp/server.py)
- [ ] FastAPI + mcp-python-sdk でStreamable HTTPサーバー構成
- [ ] list_services ツール実装
- [ ] list_operations ツール実装（Describe/List系フィルタ）
- [ ] describe_operation ツール実装（入出力スキーマ + ドキュメント）
- [ ] describe_shape ツール実装（ネスト構造体の再帰展開）
- [ ] serve サブコマンドとの統合
