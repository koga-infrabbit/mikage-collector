"""AWS API executor - handles boto3 client creation, API calls, pagination, and variable resolution."""

from __future__ import annotations

import logging
import re
from typing import Any

import boto3
import jmespath
from botocore.exceptions import ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from mikage_collector.scanner.definition import ResourceDefinition, ServiceDefinition, StepDefinition

logger = logging.getLogger(__name__)


def _is_throttling(exc: BaseException) -> bool:
    """Check if an exception is a throttling error."""
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in ("Throttling", "ThrottlingException", "RequestLimitExceeded", "TooManyRequestsException")
    return False


class SessionFactory:
    """Creates boto3 sessions with optional profile and AssumeRole support."""

    def __init__(
        self,
        profile: str | None = None,
        role_arn: str | None = None,
    ) -> None:
        self._profile = profile
        self._role_arn = role_arn
        self._base_session = boto3.Session(profile_name=profile)

    def get_session(self) -> boto3.Session:
        """Return a session, assuming role if configured."""
        if self._role_arn is None:
            return self._base_session

        sts = self._base_session.client("sts")
        creds = sts.assume_role(
            RoleArn=self._role_arn,
            RoleSessionName="mikage-collector",
        )["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )

    def create_client(self, service: str, region: str) -> Any:
        """Create a boto3 client for the given service and region."""
        session = self.get_session()
        return session.client(service, region_name=region)

    def get_account_id(self) -> str:
        """Return the AWS account ID for the current session."""
        sts = self.get_session().client("sts")
        return sts.get_caller_identity()["Account"]


def _resolve_variable(value: Any, context: dict[str, Any]) -> Any:
    """Resolve $variable references in parameter values.

    - "$varname" → context["varname"]
    - "$each" → context["each"]
    """
    if isinstance(value, str) and value.startswith("$"):
        var_name = value[1:]
        if var_name in context:
            return context[var_name]
        logger.warning("Unresolved variable: %s", value)
        return value
    return value


def _resolve_params(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Resolve all variable references in a params dict."""
    return {k: _resolve_variable(v, context) for k, v in params.items()}


def _extract_by_jmespath(data: Any, expression: str) -> Any:
    """Extract values using a JMESPath expression."""
    return jmespath.search(expression, data)


def _extract_result(response: dict[str, Any], result_key: str) -> Any:
    """Extract result from API response using result_key.

    Supports JMESPath-style expressions (e.g. "Reservations[].Instances[]").
    """
    if "[]" in result_key or "." in result_key:
        return _extract_by_jmespath(response, result_key) or []
    return response.get(result_key, [])


class StepExecutor:
    """Executes a single API step against a boto3 client."""

    @retry(
        retry=retry_if_exception(_is_throttling),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _call_api(self, client: Any, action: str, params: dict[str, Any]) -> Any:
        """Call a boto3 API with throttling retry."""
        method = getattr(client, self._to_snake_case(action))

        if client.can_paginate(self._to_snake_case(action)):
            paginator = client.get_paginator(self._to_snake_case(action))
            pages = paginator.paginate(**params) if params else paginator.paginate()
            results: list[Any] = []
            for page in pages:
                results.append(page)
            return self._merge_pages(results)

        return method(**params) if params else method()

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert PascalCase API name to snake_case for boto3."""
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @staticmethod
    def _merge_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge paginated responses into a single dict."""
        if not pages:
            return {}
        merged = {}
        for page in pages:
            for key, value in page.items():
                if key.startswith("Response") or key == "NextToken" or key == "Marker":
                    continue
                if key in merged and isinstance(value, list):
                    merged[key].extend(value)
                else:
                    merged[key] = value
        return merged

    def execute(
        self,
        client: Any,
        step: StepDefinition,
        context: dict[str, Any],
    ) -> Any:
        """Execute a step and return the extracted result."""
        params = _resolve_params(step.params, context)
        response = self._call_api(client, step.action, params)
        return _extract_result(response, step.result_key)


class ResourceExecutor:
    """Executes all steps for a resource definition, handling for_each iteration."""

    def __init__(self) -> None:
        self._step_executor = StepExecutor()

    def execute(
        self,
        client: Any,
        resource_name: str,
        resource_def: ResourceDefinition,
        scan_context: dict[str, Any],
    ) -> list[Any]:
        """Execute a resource definition and return collected results.

        Args:
            client: boto3 client for the service.
            resource_name: Name of the resource being scanned.
            resource_def: The resource definition with steps.
            scan_context: Results from previously scanned resources (for depends_on/for_each).
        """
        if resource_def.for_each:
            return self._execute_for_each(client, resource_name, resource_def, scan_context)
        return self._execute_steps(client, resource_def.steps, {})

    def _execute_steps(
        self,
        client: Any,
        steps: list[StepDefinition],
        context: dict[str, Any],
    ) -> list[Any]:
        """Execute a sequence of steps, passing results forward."""
        step_context = dict(context)
        result: list[Any] = []

        for step in steps:
            result = self._step_executor.execute(client, step, step_context)
            # Store result for next step's variable resolution
            var_name = step.result_key.split("[")[0].split(".")[-1]
            step_context[var_name] = result

        return result if isinstance(result, list) else [result]

    def _execute_for_each(
        self,
        client: Any,
        resource_name: str,
        resource_def: ResourceDefinition,
        scan_context: dict[str, Any],
    ) -> list[Any]:
        """Execute steps for each item from a parent resource."""
        for_each_expr = resource_def.for_each
        if for_each_expr is None:
            return []

        # Extract iteration items from scan_context
        items = _extract_by_jmespath(scan_context, for_each_expr)
        if not items:
            logger.debug("No items for for_each '%s' in resource '%s'", for_each_expr, resource_name)
            return []

        all_results: list[Any] = []
        for item in items:
            context = {"each": item}
            try:
                results = self._execute_steps(client, resource_def.steps, context)
                all_results.extend(results)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("AccessDeniedException", "UnauthorizedOperation", "AccessDenied"):
                    logger.warning("Access denied for %s (item=%s): %s", resource_name, item, e)
                else:
                    logger.warning("Error scanning %s (item=%s): %s", resource_name, item, e)

        return all_results


class ServiceExecutor:
    """Executes all resources for a service definition in dependency order."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._resource_executor = ResourceExecutor()

    def execute(
        self,
        service_def: ServiceDefinition,
        region: str,
    ) -> tuple[dict[str, list[Any]], list[dict[str, str]]]:
        """Scan all resources for a service definition.

        Returns:
            Tuple of (results dict, errors list).
        """
        client = self._session_factory.create_client(service_def.client, region)
        results: dict[str, list[Any]] = {}
        errors: list[dict[str, str]] = []

        execution_order = self._resolve_order(service_def)

        for resource_name in execution_order:
            resource_def = service_def.resources[resource_name]
            try:
                scan_context = results  # Previous results available for depends_on
                resource_results = self._resource_executor.execute(
                    client, resource_name, resource_def, scan_context
                )
                results[resource_name] = resource_results
                logger.info(
                    "Scanned %s.%s: %d item(s)",
                    service_def.service,
                    resource_name,
                    len(resource_results),
                )
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                msg = str(e)
                if code in ("AccessDeniedException", "UnauthorizedOperation", "AccessDenied"):
                    logger.warning("Access denied for %s.%s, skipping: %s", service_def.service, resource_name, msg)
                else:
                    logger.warning("Error scanning %s.%s: %s", service_def.service, resource_name, msg)
                errors.append({
                    "service": service_def.service,
                    "resource": resource_name,
                    "error": msg,
                })

        return results, errors

    @staticmethod
    def _resolve_order(service_def: ServiceDefinition) -> list[str]:
        """Topological sort of resources based on depends_on."""
        order: list[str] = []
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            resource = service_def.resources[name]
            if resource.depends_on and resource.depends_on in service_def.resources:
                visit(resource.depends_on)
            order.append(name)

        for name in service_def.resources:
            visit(name)

        return order
