"""Scan engine - orchestrates service definitions across regions and assembles output."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mikage_collector.scanner.definition import ServiceDefinition, load_all_definitions
from mikage_collector.scanner.executor import ServiceExecutor, SessionFactory

logger = logging.getLogger(__name__)


class ScanEngine:
    """Orchestrates scanning across services and regions."""

    def __init__(
        self,
        regions: list[str] | None = None,
        profile: str | None = None,
        role_arn: str | None = None,
    ) -> None:
        self._session_factory = SessionFactory(profile=profile, role_arn=role_arn)
        self._service_executor = ServiceExecutor(self._session_factory)
        self._regions = regions or self._detect_region()

    def _detect_region(self) -> list[str]:
        """Detect the default region from the session."""
        session = self._session_factory.get_session()
        region = session.region_name or "us-east-1"
        return [region]

    def scan(
        self,
        services: list[str] | None = None,
        custom_dirs: list[Path] | None = None,
        definition_files: list[Path] | None = None,
    ) -> dict[str, Any]:
        """Run a full scan and return the result JSON structure.

        Args:
            services: Filter to specific service names.
            custom_dirs: Additional definition directories.
            definition_files: Specific definition files (overrides builtin+custom).
        """
        definitions = load_all_definitions(
            custom_dirs=custom_dirs,
            definition_files=definition_files,
            services=services,
        )

        if not definitions:
            logger.warning("No definitions loaded, nothing to scan.")
            return self._build_output({}, [], definitions)

        account_id = self._get_account_id()
        all_resources: dict[str, dict[str, list[Any]]] = {}
        all_errors: list[dict[str, str]] = []

        for region in self._regions:
            logger.info("Scanning region: %s", region)
            for defn in definitions:
                logger.info("Scanning service: %s", defn.service)
                results, errors = self._service_executor.execute(defn, region)

                if defn.service not in all_resources:
                    all_resources[defn.service] = {}
                for resource_name, items in results.items():
                    if resource_name in all_resources[defn.service]:
                        all_resources[defn.service][resource_name].extend(items)
                    else:
                        all_resources[defn.service][resource_name] = items

                for err in errors:
                    err["region"] = region
                all_errors.extend(errors)

        return self._build_output(all_resources, all_errors, definitions, account_id)

    def _get_account_id(self) -> str:
        """Get the AWS account ID, with fallback."""
        try:
            return self._session_factory.get_account_id()
        except Exception as e:
            logger.warning("Could not determine account ID: %s", e)
            return "unknown"

    def _build_output(
        self,
        resources: dict[str, dict[str, list[Any]]],
        errors: list[dict[str, str]],
        definitions: list[ServiceDefinition],
        account_id: str = "unknown",
    ) -> dict[str, Any]:
        """Assemble the final JSON output structure."""
        total = sum(
            len(items)
            for svc in resources.values()
            for items in svc.values()
        )
        by_service = {
            svc_name: sum(len(items) for items in svc_resources.values())
            for svc_name, svc_resources in resources.items()
        }
        definitions_used = [d.service for d in definitions]

        summary: dict[str, Any] = {
            "total_resources": total,
            "by_service": by_service,
            "definitions_used": definitions_used,
        }
        if errors:
            summary["errors"] = errors

        return {
            "scan_id": str(uuid.uuid4()),
            "account_id": account_id,
            "regions": self._regions,
            "scan_date": datetime.now(timezone.utc).isoformat(),
            "resources": resources,
            "summary": summary,
        }
