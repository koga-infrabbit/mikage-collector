# AutoCollector 設計

## 参照

#[[file:../../../../IntegratedMonitoringSystem/Repositories/AutoCollector/docs/design.md]]

## プロジェクト構成

```
mikage-collector/
├── pyproject.toml
├── Dockerfile
├── README.md
├── src/
│   └── mikage_collector/
│       ├── __init__.py
│       ├── cli.py                  # CLIエントリポイント (click)
│       ├── scanner/
│       │   ├── __init__.py
│       │   ├── engine.py           # スキャンエンジン本体
│       │   ├── definition.py       # 定義ファイルローダー・バリデーション
│       │   └── executor.py         # boto3 API実行 (ステップ実行・ページネーション)
│       ├── mcp/
│       │   ├── __init__.py
│       │   └── server.py           # MCP Server (Streamable HTTP)
│       └── definitions/
│           └── builtin/
│               ├── ec2.yaml
│               ├── rds.yaml
│               ├── ecs.yaml
│               ├── lambda.yaml
│               ├── elbv2.yaml
│               └── s3.yaml
└── tests/
    ├── __init__.py
    ├── test_definition.py
    ├── test_engine.py
    └── test_executor.py
```

## コンポーネント設計

### 1. cli.py - CLIエントリポイント

click ベース。2つのサブコマンド:
- `scan`: スキャンエンジン実行
- `serve`: MCPサーバー起動

```
autocollector scan [OPTIONS]
autocollector serve --mcp --port 8080
```

### 2. scanner/definition.py - 定義ファイルローダー

- YAML読み込み + pydanticバリデーション
- ビルトインディレクトリ（パッケージ同梱）+ カスタムディレクトリの両方を走査
- 不正な定義はスキップしてログ出力

定義ファイルのデータモデル:
```python
class StepDefinition(BaseModel):
    action: str                    # boto3 API名 (例: "DescribeInstances")
    params: dict[str, Any] = {}    # パラメータ ($変数参照あり)
    result_key: str                # レスポンスから抽出するキー

class ResourceDefinition(BaseModel):
    steps: list[StepDefinition]
    depends_on: str | None = None  # 依存リソース名
    for_each: str | None = None    # イテレーション対象 (例: "clusters[].clusterArn")

class ServiceDefinition(BaseModel):
    service: str                   # boto3名前空間 (例: "ec2")
    client: str                    # boto3クライアント名
    resources: dict[str, ResourceDefinition]
```

### 3. scanner/executor.py - API実行

- boto3クライアント生成 + API呼び出し
- ページネーション自動処理（boto3 paginator使用）
- `$変数参照` の解決（前ステップの結果を次ステップのパラメータに注入）
- `for_each` のイテレーション処理
- 権限不足時のスキップ（ClientError catch）

### 4. scanner/engine.py - スキャンエンジン

- 定義ファイル群を受け取り、依存順にソートして実行
- リージョンごとにスキャン
- 結果をJSON構造に組み立て
- summaryの生成（リソース数、使用定義、エラー）

### 5. mcp/server.py - MCPサーバー

- FastAPI + mcp-python-sdk (Streamable HTTP)
- 4ツール: list_services, list_operations, describe_operation, describe_shape
- boto3 session.get_available_services() / client.meta.service_model を使用

## 定義ファイル変数解決

ステップ間の変数参照ルール:
- `$変数名`: 前ステップの result_key で取得した値を参照
- `$each`: for_each イテレーション中の現在の要素
- JMESPath風のパス: `clusters[].clusterArn` でネスト配列からフィールド抽出

## ページネーション

boto3のpaginatorが使えるAPIはpaginatorを使用。
paginatorが存在しないAPIは単発呼び出し。
判定は `client.can_paginate(operation_name)` で動的に行う。

## エラーハンドリング方針

- サービス単位でtry/catch、失敗してもスキャン全体は継続
- AccessDenied / UnauthorizedOperation → スキップ、summaryにerrorとして記録
- Throttling → exponential backoff でリトライ（boto3デフォルト + tenacity）
- 定義ファイル構文エラー → 起動時にバリデーション、不正な定義はスキップ

## 依存ライブラリ

| ライブラリ | 用途 |
|-----------|------|
| boto3 | AWS SDK |
| click | CLI |
| pydantic | 定義ファイルバリデーション |
| pyyaml | YAML読み込み |
| jmespath | パス式評価 |
| tenacity | リトライ |
| fastapi | MCPサーバー |
| uvicorn | ASGIサーバー |
| mcp | MCP Python SDK |
