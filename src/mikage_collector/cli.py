"""CLI entry point for mikage-collector."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress info logging.")
def main(verbose: bool, quiet: bool) -> None:
    """Mikage Collector - AWS resource scanner."""
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


@main.command()
@click.option("--region", "-r", multiple=True, help="AWS region(s) to scan.")
@click.option("--service", "-s", multiple=True, help="Service name(s) to scan.")
@click.option("--definitions", "-d", multiple=True, help="Custom definition directory.")
@click.option("--definition-file", multiple=True, help="Specific definition file(s).")
@click.option("--role-arn", help="IAM role ARN for cross-account access.")
@click.option("--profile", "-p", help="AWS profile name.")
@click.option("--output", "-o", help="Output file path (default: stdout).")
def scan(
    region: tuple[str, ...],
    service: tuple[str, ...],
    definitions: tuple[str, ...],
    definition_file: tuple[str, ...],
    role_arn: str | None,
    profile: str | None,
    output: str | None,
) -> None:
    """Scan AWS resources using definition files."""
    from mikage_collector.scanner.engine import ScanEngine

    engine = ScanEngine(
        regions=list(region) if region else None,
        profile=profile,
        role_arn=role_arn,
    )

    result = engine.scan(
        services=list(service) if service else None,
        custom_dirs=[Path(d) for d in definitions] if definitions else None,
        definition_files=[Path(f) for f in definition_file] if definition_file else None,
    )

    json_output = json.dumps(result, indent=2, default=str, ensure_ascii=False)

    if output:
        Path(output).write_text(json_output, encoding="utf-8")
        click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(json_output)


@main.command()
@click.option("--port", default=8080, help="Port for MCP server.")
@click.option("--host", default="0.0.0.0", help="Host to bind.")
def serve(port: int, host: str) -> None:
    """Start the boto3 introspection MCP server."""
    from mikage_collector.mcp.server import create_app

    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
