# AutoCollector 要件定義

## 概要

AWSアカウント内の既存リソースを自動スキャンし、構造化JSON（boto3レスポンス互換）で出力するツール。
現実の構成を正確に記述することが責務。判断・分析・保存は行わない。

2つの機能を提供する:
1. スキャンエンジン: 定義ファイル駆動でAWSリソースをスキャン → JSON出力
2. boto3イントロスペクションMCPサーバー: boto3のサービスモデルをMCP経由で公開

## 参照設計書

#[[file:../../../../IntegratedMonitoringSystem/Repositories/AutoCollector/docs/design.md]]

## 機能要件

### FR-1: スキャンエンジン（CLI）

- 定義ファイル（YAML）駆動でAWSリソースをスキャン
- ビルトイン定義（EC2, VPC, RDS, ALB, ECS, Lambda等）を同梱
- ユーザー定義（カスタムYAML）を追加ディレクトリから読み込み可能
- API呼び出しパターン3種対応: describe一発 / list→describe / listのみ
- 出力はJSON（stdout or ファイル）、boto3レスポンスそのまま保持
- 一部リソース取得失敗でもスキャン全体は継続（エラーはsummaryに記録）
- 定義ファイルの構文エラーは起動時バリデーション、不正な定義はスキップ

### FR-2: CLIインターフェース

- `autocollector scan` でデフォルトスキャン実行
- `--region` でリージョン指定（複数可）
- `--service` で特定サービスのみスキャン
- `--definitions` でカスタム定義ディレクトリ追加
- `--definition-file` で特定の定義ファイルのみ実行
- `--role-arn` でクロスアカウント（AssumeRole）
- `--profile` でAWSプロファイル指定
- `--output` で出力先ファイル指定（デフォルトstdout）

### FR-3: boto3イントロスペクションMCPサーバー

- Streamable HTTP（FastAPI or Starlette）で提供
- `autocollector serve --mcp --port 8080` で起動
- 4ツール提供:
  - `list_services`: boto3サポートサービス一覧
  - `list_operations`: 指定サービスのオペレーション一覧（Describe/List系フィルタ可）
  - `describe_operation`: 入出力スキーマ + ドキュメント
  - `describe_shape`: ネスト構造体の詳細

### FR-4: 認証

- boto3デフォルトクレデンシャルチェーンに依存
- AutoCollector自身に認証機構を持たせない
- 環境変数、~/.aws/credentials、IAMロール、SSO等すべて対応

## 非機能要件

### NFR-1: 実装言語・技術スタック

- Python 3.11+
- boto3
- YAML定義ファイル
- JSON出力
- pip install / Dockerイメージで配布

### NFR-2: 設計原則

- ワンショット実行（常駐しない、MCPサーバーモード除く）
- LLM不使用、単独駆動
- 保存先は関知しない（出力するだけ）
- AutoCollectorは「手足」であり「頭脳」は持たない

## スコープ外

- スキャン結果の保存・バージョン管理（統合層の責務）
- スキャン結果の分析・依存関係解決（統合層の責務）
- 何をスキャンするか判断する自律探索（統合層の責務）
- 未知サービスの定義YAML生成（統合層LLMの責務）
