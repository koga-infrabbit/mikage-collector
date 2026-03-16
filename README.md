# Mikage Collector

定義ファイル駆動のAWSリソーススキャナー + boto3イントロスペクションMCPサーバー。

AWSアカウント内のリソースをYAML定義に従ってスキャンし、構造化JSONで出力する。
判断・分析・保存は行わない。スキャンして返すだけ。

## 機能

- **スキャンエンジン**: YAML定義ファイルに従ってboto3 APIを実行し、リソース情報をJSON出力
- **MCP Server**: boto3サービスモデルのイントロスペクション + スキャン実行をStreamable HTTP経由で提供

## インストール

```bash
pip install .

# 開発用
pip install -e ".[dev]"
```

## CLI

### scan - リソーススキャン

```bash
# デフォルト: ec2のみスキャン
autocollector scan

# サービス指定（カンマ区切り対応）
autocollector scan -s ec2,rds,ecs

# 複数指定（-s を複数回）
autocollector scan -s ec2 -s rds

# 全ビルトイン定義でフルスキャン
autocollector scan -s all

# リージョン指定
autocollector scan -r ap-northeast-1

# 複数リージョン
autocollector scan -r ap-northeast-1 -r us-east-1

# クロスアカウント（AssumeRole）
autocollector scan --role-arn arn:aws:iam::123456789012:role/ReadOnlyRole

# プロファイル指定
autocollector scan -p my-profile

# ファイル出力
autocollector scan -o result.json

# カスタム定義ディレクトリ追加
autocollector scan -d /path/to/custom/definitions/

# 特定の定義ファイルのみ実行
autocollector scan --definition-file /path/to/custom.yaml

# デバッグログ
autocollector -v scan -s ec2
```

### serve - MCP Server起動

```bash
autocollector serve --port 8080
```

## Docker

### ビルド

```bash
docker compose build
```

### スキャン実行

`.env` を設定してから:

```bash
# .env の scan_target でサービス指定
./scan.sh
```

### MCP Server起動

```bash
./serve.sh
```

### .env 設定

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=
AWS_PROFILE=my-profile
serve_port=8888
scan_target=ec2
```

`~/.aws` がコンテナにマウントされるため、プロファイル認証も利用可能。

## ビルトイン定義

| サービス | リソース |
|---------|---------|
| ec2 | instances, vpcs, subnets, security_groups, volumes, network_interfaces, addresses |
| ecs | clusters, services |
| elbv2 | load_balancers, listeners, target_groups |
| lambda | functions |
| rds | db_instances, db_clusters |
| s3 | buckets |
| dynamodb | tables, table_details |
| apigateway | rest_apis |
| apigatewayv2 | apis |
| route53 | hosted_zones, record_sets |
| efs | file_systems |
| servicediscovery | namespaces, services |

## カスタム定義ファイル

YAML形式で独自のスキャン定義を追加できる。

```yaml
service: apprunner
client: apprunner
resources:
  services:
    steps:
      - action: ListServices
        result_key: ServiceSummaryList
```

### 定義ファイルの構文

```yaml
service: <boto3サービス名>
client: <boto3クライアント名>
resources:
  <リソース名>:
    steps:
      - action: <API操作名(PascalCase)>
        params:                    # オプション
          <パラメータ名>: <値 or $変数>
        result_key: <レスポンスキー>  # JMESPath対応
    depends_on: <依存リソース名>     # オプション
    for_each: <イテレーション式>     # オプション
```

### 変数参照

- `$変数名`: 前ステップの result_key で取得した値
- `$each`: for_each イテレーション中の現在の要素

## MCP Server ツール一覧

### イントロスペクション

| ツール | 説明 |
|-------|------|
| `list_services` | boto3がサポートする全AWSサービス一覧 |
| `list_operations` | 指定サービスのAPI操作一覧（Describe/List系フィルタ可） |
| `describe_operation` | API操作の入出力スキーマ + ドキュメント |
| `describe_shape` | ネスト構造体の再帰的な詳細展開 |

### スキャン

| ツール | 説明 |
|-------|------|
| `list_definitions` | 利用可能なビルトイン定義一覧 |
| `scan` | リソーススキャン実行（サービス指定必須、インラインYAML定義対応） |

### MCP接続設定例（Kiro / Claude Desktop等）

```json
{
  "mcpServers": {
    "mikage-collector": {
      "url": "http://localhost:8888/mcp"
    }
  }
}
```

## 認証

boto3のデフォルトクレデンシャルチェーンに依存:

1. 環境変数（`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`）
2. `~/.aws/credentials` / `~/.aws/config`（`--profile` / `-p`）
3. ECSタスクロール / EC2インスタンスプロファイル
4. SSO / OIDC

クロスアカウントは `--role-arn` でAssumeRole。

## ライセンス

Apache License 2.0
