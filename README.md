# Mikage Collector

AWS resource scanner with definition-file-driven scanning and boto3 introspection MCP server.

## Usage

```bash
# Install
pip install .

# Scan AWS resources
autocollector scan --region ap-northeast-1

# Start MCP server
autocollector serve --port 8080
```
