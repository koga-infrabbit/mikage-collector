# AutoCollector タスク

## Task 1: プロジェクト基盤セットアップ
- [x] pyproject.toml 作成（プロジェクトメタデータ、依存関係、エントリポイント）
- [x] src/mikage_collector/__init__.py 作成
- [x] パッケージ構成（scanner/, mcp/, definitions/builtin/）のディレクトリ・__init__.py作成
- [x] Dockerfile 作成

## Task 2: 定義ファイルローダー (scanner/definition.py)
- [x] Pydanticモデル定義（StepDefinition, ResourceDefinition, ServiceDefinition）
- [x] YAMLファイル読み込み + バリデーション
- [x] ビルトインディレクトリ（パッケージ同梱）からの定義読み込み
- [x] カスタムディレクトリからの定義読み込み
- [x] 不正な定義のスキップ + ログ出力

## Task 3: API実行エンジン (scanner/executor.py)
- [x] boto3クライアント生成（リージョン、プロファイル、AssumeRole対応）
- [x] 単一ステップのAPI実行（action → result_key抽出）
- [x] ページネーション自動処理（can_paginate判定 → paginator使用）
- [x] $変数参照の解決（前ステップ結果 → 次ステップパラメータ注入）
- [x] for_each イテレーション処理
- [x] JMESPath式によるネスト配列からのフィールド抽出
- [x] エラーハンドリング（AccessDenied スキップ、Throttling リトライ）

## Task 4: スキャンエンジン (scanner/engine.py)
- [x] 定義ファイル群の依存順ソート（depends_on解決）
- [x] リージョンごとのスキャン実行ループ
- [x] 結果のJSON構造組み立て（設計書の出力フォーマット準拠）
- [x] summary生成（total_resources, by_service, definitions_used, errors）

## Task 5: CLIエントリポイント (cli.py)
- [x] click ベースのCLI構成（scan / serve サブコマンド）
- [x] scan サブコマンド: --region, --service, --definitions, --definition-file, --role-arn, --profile, --output
- [x] JSON出力（stdout / ファイル）
- [x] ログ出力設定（--verbose / --quiet）

## Task 6: ビルトイン定義ファイル作成
- [x] ec2.yaml（instances, vpcs, subnets, security_groups）
- [x] rds.yaml（db_instances, db_clusters）
- [x] ecs.yaml（clusters, services）※ list→describe パターン
- [x] lambda.yaml（functions）
- [x] elbv2.yaml（load_balancers, target_groups）
- [x] s3.yaml（buckets）※ グローバルサービス

## Task 7: MCP Server (mcp/server.py)
- [x] FastAPI + mcp-python-sdk でStreamable HTTPサーバー構成
- [x] list_services ツール実装
- [x] list_operations ツール実装（Describe/List系フィルタ）
- [x] describe_operation ツール実装（入出力スキーマ + ドキュメント）
- [x] describe_shape ツール実装（ネスト構造体の再帰展開）
- [x] serve サブコマンドとの統合
