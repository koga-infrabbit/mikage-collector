"""MCP Server for boto3 service model introspection."""

from __future__ import annotations

import re
from typing import Any

import boto3
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mikage-collector-introspection")

_session = boto3.Session()


def _get_service_model(service: str) -> Any:
    """Get the botocore service model for a service."""
    client = _session.client(service)
    return client.meta.service_model


def _shape_to_dict(shape: Any, max_depth: int = 3, depth: int = 0) -> dict[str, Any]:
    """Convert a botocore shape to a serializable dict."""
    if depth >= max_depth:
        return {"type": shape.type_name}

    result: dict[str, Any] = {"type": shape.type_name}

    if hasattr(shape, "documentation") and shape.documentation:
        doc = shape.documentation
        # Strip HTML tags
        doc = re.sub(r"<[^>]+>", "", doc).strip()
        if doc:
            result["documentation"] = doc[:500]

    if shape.type_name == "structure" and hasattr(shape, "members"):
        members = {}
        for name, member_shape in shape.members.items():
            members[name] = _shape_to_dict(member_shape, max_depth, depth + 1)
        result["members"] = members
    elif shape.type_name == "list" and hasattr(shape, "member"):
        result["member"] = _shape_to_dict(shape.member, max_depth, depth + 1)

    elif shape.type_name == "map" and hasattr(shape, "key") and hasattr(shape, "value"):
        result["key"] = _shape_to_dict(shape.key, max_depth, depth + 1)
        result["value"] = _shape_to_dict(shape.value, max_depth, depth + 1)

    return result


@mcp.tool()
def list_services(keyword: str | None = None) -> dict[str, Any]:
    """List all AWS services supported by boto3.

    Args:
        keyword: Optional keyword to filter service names.
    """
    services = _session.get_available_services()
    if keyword:
        kw = keyword.lower()
        services = [s for s in services if kw in s.lower()]
    return {"total": len(services), "services": sorted(services)}


@mcp.tool()
def list_operations(service: str, filter: str | None = None) -> dict[str, Any]:
    """List operations for an AWS service.

    Args:
        service: boto3 service name (e.g. "ec2", "ecs").
        filter: Optional filter - "describe_list" to show only Describe/List operations.
    """
    model = _get_service_model(service)
    operations = []

    for op_name in sorted(model.operation_names):
        if filter == "describe_list":
            if not (op_name.startswith("Describe") or op_name.startswith("List") or op_name.startswith("Get")):
                continue

        op_model = model.operation_model(op_name)
        doc = ""
        if op_model.documentation:
            doc = re.sub(r"<[^>]+>", "", op_model.documentation).strip()[:200]

        operations.append({"name": op_name, "documentation": doc})

    return {"service": service, "total": len(operations), "operations": operations}


@mcp.tool()
def describe_operation(service: str, operation: str) -> dict[str, Any]:
    """Describe an AWS API operation including input/output schemas and documentation.

    Args:
        service: boto3 service name (e.g. "ecs").
        operation: Operation name (e.g. "DescribeClusters").
    """
    model = _get_service_model(service)
    op_model = model.operation_model(operation)

    doc = ""
    if op_model.documentation:
        doc = re.sub(r"<[^>]+>", "", op_model.documentation).strip()[:500]

    result: dict[str, Any] = {
        "name": operation,
        "documentation": doc,
    }

    if op_model.input_shape:
        input_members = {}
        required = set(getattr(op_model.input_shape, "required_members", []))
        for name, shape in op_model.input_shape.members.items():
            member_info = _shape_to_dict(shape, max_depth=2)
            member_info["required"] = name in required
            input_members[name] = member_info
        result["input"] = {"members": input_members}

    if op_model.output_shape:
        output_members = {}
        for name, shape in op_model.output_shape.members.items():
            output_members[name] = _shape_to_dict(shape, max_depth=2)
        result["output"] = {"members": output_members}

    return result


@mcp.tool()
def describe_shape(service: str, operation: str, shape_path: str) -> dict[str, Any]:
    """Describe a nested shape within an operation's output, with recursive detail.

    Args:
        service: boto3 service name (e.g. "ec2").
        operation: Operation name (e.g. "DescribeInstances").
        shape_path: Dot/bracket path to the shape (e.g. "Reservations[].Instances[]").
    """
    model = _get_service_model(service)
    op_model = model.operation_model(operation)

    if not op_model.output_shape:
        return {"error": f"Operation {operation} has no output shape"}

    # Navigate the shape path
    current_shape = op_model.output_shape
    parts = [p for p in re.split(r"[\.\[\]]+", shape_path) if p]

    for part in parts:
        if hasattr(current_shape, "members") and part in current_shape.members:
            current_shape = current_shape.members[part]
        elif hasattr(current_shape, "member"):
            # List type - descend into member, then look for the part
            current_shape = current_shape.member
            if hasattr(current_shape, "members") and part in current_shape.members:
                current_shape = current_shape.members[part]
        else:
            return {"error": f"Could not resolve path segment '{part}' in {shape_path}"}

    # If we ended on a list, unwrap to the member
    if current_shape.type_name == "list" and hasattr(current_shape, "member"):
        current_shape = current_shape.member

    result = _shape_to_dict(current_shape, max_depth=4)
    if "members" in result:
        result["total_fields"] = len(result["members"])

    return result


def create_app() -> Any:
    """Create the ASGI app for the MCP server."""
    return mcp.streamable_http_app()
