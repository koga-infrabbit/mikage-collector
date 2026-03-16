"""Definition file loader and validation for AWS resource scan definitions."""

from __future__ import annotations

import logging
from importlib import resources as pkg_resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class StepDefinition(BaseModel):
    """A single API call step within a resource scan."""

    action: str
    params: dict[str, Any] = {}
    result_key: str


class ResourceDefinition(BaseModel):
    """Definition for scanning a specific resource type."""

    steps: list[StepDefinition]
    depends_on: str | None = None
    for_each: str | None = None


class ServiceDefinition(BaseModel):
    """Top-level definition for scanning an AWS service."""

    service: str
    client: str
    resources: dict[str, ResourceDefinition]


def parse_definitions_from_yaml(yaml_text: str) -> list[ServiceDefinition]:
    """Parse one or more ServiceDefinitions from a YAML string.

    Supports both a single document and multi-document YAML (separated by '---').
    Returns a list of valid definitions; invalid documents are skipped with a warning.
    """
    definitions: list[ServiceDefinition] = []
    try:
        docs = list(yaml.safe_load_all(yaml_text))
    except yaml.YAMLError as e:
        logger.warning("YAML parse error in inline definition: %s", e)
        return definitions

    for i, data in enumerate(docs):
        if data is None:
            continue
        try:
            definitions.append(ServiceDefinition.model_validate(data))
        except ValidationError as e:
            logger.warning("Validation error in inline definition (doc %d): %s", i, e)

    return definitions


def load_definition_file(path: Path) -> ServiceDefinition | None:
    """Load and validate a single YAML definition file.

    Returns None if the file is invalid (logs warning and skips).
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            logger.warning("Empty definition file: %s", path)
            return None
        return ServiceDefinition.model_validate(data)
    except yaml.YAMLError as e:
        logger.warning("YAML parse error in %s: %s", path, e)
        return None
    except ValidationError as e:
        logger.warning("Validation error in %s: %s", path, e)
        return None


def _load_definitions_from_dir(directory: Path) -> list[ServiceDefinition]:
    """Load all .yaml/.yml definitions from a directory."""
    definitions: list[ServiceDefinition] = []
    if not directory.is_dir():
        logger.debug("Definition directory does not exist: %s", directory)
        return definitions

    for path in sorted(directory.glob("*.yaml")):
        defn = load_definition_file(path)
        if defn is not None:
            definitions.append(defn)

    for path in sorted(directory.glob("*.yml")):
        defn = load_definition_file(path)
        if defn is not None:
            definitions.append(defn)

    return definitions


def get_builtin_definitions_dir() -> Path:
    """Return the path to the builtin definitions directory shipped with the package."""
    return Path(__file__).parent.parent / "definitions" / "builtin"


def load_builtin_definitions() -> list[ServiceDefinition]:
    """Load all builtin definition files shipped with the package."""
    return _load_definitions_from_dir(get_builtin_definitions_dir())


def load_custom_definitions(directories: list[Path]) -> list[ServiceDefinition]:
    """Load definitions from one or more custom directories."""
    definitions: list[ServiceDefinition] = []
    for directory in directories:
        definitions.extend(_load_definitions_from_dir(directory))
    return definitions


def load_definition_files(paths: list[Path]) -> list[ServiceDefinition]:
    """Load specific definition files by path."""
    definitions: list[ServiceDefinition] = []
    for path in paths:
        defn = load_definition_file(path)
        if defn is not None:
            definitions.append(defn)
    return definitions


def load_all_definitions(
    custom_dirs: list[Path] | None = None,
    definition_files: list[Path] | None = None,
    services: list[str] | None = None,
) -> list[ServiceDefinition]:
    """Load builtin + custom definitions, optionally filtered by service name.

    Args:
        custom_dirs: Additional directories to scan for definitions.
        definition_files: Specific definition files to load (skips builtin/custom dirs).
        services: If provided, only return definitions matching these service names.
    """
    if definition_files:
        definitions = load_definition_files(definition_files)
    else:
        definitions = load_builtin_definitions()
        if custom_dirs:
            definitions.extend(load_custom_definitions(custom_dirs))

    if services:
        service_set = set(services)
        definitions = [d for d in definitions if d.service in service_set]

    logger.info("Loaded %d definition(s)", len(definitions))
    return definitions
