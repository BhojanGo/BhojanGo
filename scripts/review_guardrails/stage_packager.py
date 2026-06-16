#!/usr/bin/env python3
"""
stage_packager.py

Deterministic review-export packager for BhojanGo stage contracts.

Purpose
-------
This script is a mechanical helper for Kimchi and reviewers. It reads a
stage contract JSON, collects every expected source/config/test/evidence/
screenshot/guardrail file declared by the contract, copies missing-but-existing
repo files into the review export folder while preserving repo-relative paths,
fails when required repo files are missing, writes a packager report, writes a
zip-listing log, and creates the final review zip.

It is intentionally not an LLM/auditor. It does not decide business quality.
It only performs deterministic packaging and mechanical integrity checks.

Design rules
------------
- No third-party dependencies.
- Repo-relative paths only.
- No path traversal.
- No flattened changed/reference folders.
- No __MACOSX/.DS_Store/node_modules/.venv/.next/build artifacts.
- No secrets such as .env files unless the code is explicitly changed later
  to support a reviewed allowlist. Default is to fail closed.
- Contract drives file inclusion.
- Generated packager outputs are included in the export and zip.

Typical usage
-------------
From repo root:

    python scripts/review_guardrails/stage_packager.py \
      --contract review_contracts/SPR-02-v3.contract.json

Optional:

    python scripts/review_guardrails/stage_packager.py \
      --repo-root /path/to/BhojanGo \
      --contract review_contracts/SPR-02-v3.contract.json \
      --clean

Exit codes
----------
0 = package created and mechanical packaging status PASS
1 = package created but mechanical packaging status PARTIAL/NO-GO
2 = invalid arguments / invalid repo / unreadable contract
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import json
import os
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL"
STATUS_NO_GO = "NO-GO"

DEFAULT_REPO_MARKERS = ("package.json", "pnpm-workspace.yaml")

DEFAULT_EXCLUDE_GLOBS = (
    "__MACOSX",
    "__MACOSX/*",
    ".DS_Store",
    "*/.DS_Store",
    "node_modules",
    "node_modules/*",
    "*/node_modules/*",
    ".venv",
    ".venv/*",
    "*/.venv/*",
    ".next",
    ".next/*",
    "*/.next/*",
    "dist",
    "dist/*",
    "*/dist/*",
    "build",
    "build/*",
    "*/build/*",
    "*.pyc",
    "*/__pycache__/*",
    "*.zip",
)

DEFAULT_FORBIDDEN_ZIP_REGEX = (
    r"(^|/)__MACOSX(/|$)",
    r"(^|/)\.DS_Store$",
    r"(^|/)node_modules(/|$)",
    r"(^|/)\.venv(/|$)",
    r"(^|/)\.next(/|$)",
    r"(^|/)dist(/|$)",
    r"(^|/)build(/|$)",
    r"(^|/)changed(/|$)",
    r"(^|/)reference(/|$)",
)

# Fail-closed secret patterns. These are deliberately stricter than generic
# exclude patterns. Review zips should not carry runtime secrets.
DEFAULT_SECRET_GLOBS = (
    ".env",
    ".env.*",
    "*/.env",
    "*/.env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*id_rsa*",
    "*id_dsa*",
)


@dataclasses.dataclass
class FileRequirement:
    """A single repo-relative file/directory requirement collected from a contract."""

    path: str
    required: bool = True
    sources: Set[str] = dataclasses.field(default_factory=set)
    artifact_types: Set[str] = dataclasses.field(default_factory=set)
    generated_by_packager: bool = False

    def merge(
        self,
        *,
        required: bool,
        source: str,
        artifact_type: Optional[str] = None,
        generated_by_packager: bool = False,
    ) -> None:
        self.required = self.required or required
        self.sources.add(source)
        if artifact_type:
            self.artifact_types.add(artifact_type)
        self.generated_by_packager = self.generated_by_packager or generated_by_packager


@dataclasses.dataclass
class CopyRecord:
    path: str
    status: str
    reason: str
    required: bool
    sources: List[str]
    artifact_types: List[str]
    bytes_copied: int = 0


@dataclasses.dataclass
class PackagerConfig:
    repo_root: Path
    contract_path: Path
    clean_output_dir: bool = False
    dry_run: bool = False
    verbose: bool = False


class PackagerError(Exception):
    """Fatal packager error."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PackagerError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PackagerError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_relative_repo_path(raw: str) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    value = raw.replace("\\", "/")
    if value.startswith("/") or value.startswith("./"):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    parts = value.split("/")
    if any(part == ".." for part in parts):
        return False
    return True


def normalize_rel_path(raw: str) -> str:
    value = raw.replace("\\", "/").strip()
    while "//" in value:
        value = value.replace("//", "/")
    value = value.rstrip("/")
    if not is_relative_repo_path(value):
        raise PackagerError(f"Invalid repo-relative path: {raw!r}")
    return value


def safe_rel_to_path(repo_root: Path, rel_path: str) -> Path:
    rel = normalize_rel_path(rel_path)
    candidate = (repo_root / rel).resolve()
    repo_resolved = repo_root.resolve()
    try:
        candidate.relative_to(repo_resolved)
    except ValueError as exc:
        raise PackagerError(f"Path escapes repo root: {rel_path}") from exc
    return candidate


def infer_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if all((candidate / marker).exists() for marker in DEFAULT_REPO_MARKERS):
            return candidate
    return current


def validate_repo_root(repo_root: Path, contract: Mapping[str, Any]) -> List[str]:
    warnings: List[str] = []
    repo = contract.get("repository") or {}
    markers = repo.get("repo_markers") or list(DEFAULT_REPO_MARKERS)
    for marker in markers:
        try:
            marker_path = safe_rel_to_path(repo_root, marker)
        except PackagerError:
            warnings.append(f"Invalid repo marker path in contract: {marker!r}")
            continue
        if not marker_path.exists():
            warnings.append(f"Repo marker missing: {marker}")
    return warnings


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def dict_get(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    node: Any = mapping
    for key in keys:
        if not isinstance(node, Mapping):
            return default
        node = node.get(key)
    return default if node is None else node


def iter_file_set_paths(file_set: Optional[Mapping[str, Any]]) -> Iterable[Tuple[str, str]]:
    """Yield (bucket, path) for paths inside a schema file_set object."""
    if not isinstance(file_set, Mapping):
        return
    for bucket in ("read", "edit", "include_in_zip", "evidence", "screenshots"):
        for path in as_list(file_set.get(bucket)):
            if isinstance(path, str):
                yield bucket, path


def iter_validator_paths(validator: Mapping[str, Any]) -> Iterable[Tuple[str, str]]:
    """Yield (source_label, path) values referenced by a validator."""
    if not isinstance(validator, Mapping):
        return
    validator_type = str(validator.get("type") or "")
    if isinstance(validator.get("path"), str):
        # file_not_exists and zip_not_contains are not necessarily inclusion requirements.
        if validator_type not in {"file_not_exists", "zip_not_contains", "code_regex_not_exists"}:
            yield f"validator:{validator.get('validator_id', 'unknown')}:path", validator["path"]
    if isinstance(validator.get("paths"), list):
        for path in validator["paths"]:
            if isinstance(path, str):
                yield f"validator:{validator.get('validator_id', 'unknown')}:paths", path
    if isinstance(validator.get("zip_path"), str):
        yield f"validator:{validator.get('validator_id', 'unknown')}:zip_path", validator["zip_path"]


class ContractPathCollector:
    """Collect file requirements from the contract JSON."""

    def __init__(self, contract: Mapping[str, Any], contract_rel_path: Optional[str]) -> None:
        self.contract = contract
        self.contract_rel_path = contract_rel_path
        self.requirements: Dict[str, FileRequirement] = {}

    def add(
        self,
        raw_path: Optional[str],
        *,
        required: bool,
        source: str,
        artifact_type: Optional[str] = None,
        generated_by_packager: bool = False,
    ) -> None:
        if not raw_path or not isinstance(raw_path, str):
            return
        rel_path = normalize_rel_path(raw_path)
        requirement = self.requirements.get(rel_path)
        if requirement is None:
            requirement = FileRequirement(
                path=rel_path,
                required=required,
                sources={source},
                artifact_types=set([artifact_type]) if artifact_type else set(),
                generated_by_packager=generated_by_packager,
            )
            self.requirements[rel_path] = requirement
        else:
            requirement.merge(
                required=required,
                source=source,
                artifact_type=artifact_type,
                generated_by_packager=generated_by_packager,
            )

    def collect(self) -> Dict[str, FileRequirement]:
        self._collect_repository_files()
        self._collect_review_export_files()
        self._collect_global_files()
        self._collect_stage_artifacts()
        self._collect_task_files()
        self._collect_kimchi_updates()
        self._collect_metrics_files()
        self._collect_generated_packager_files()
        return dict(sorted(self.requirements.items(), key=lambda item: item[0]))

    def _collect_repository_files(self) -> None:
        repository = self.contract.get("repository") or {}
        folder_structure = repository.get("folder_structure_path")
        if folder_structure:
            self.add(folder_structure, required=True, source="repository.folder_structure_path", artifact_type="documentation")

        for path in as_list(repository.get("source_of_truth_files")):
            if isinstance(path, str):
                self.add(path, required=True, source="repository.source_of_truth_files", artifact_type="documentation")

        for marker in as_list(repository.get("repo_markers")):
            if isinstance(marker, str):
                self.add(marker, required=True, source="repository.repo_markers", artifact_type="config")

    def _collect_review_export_files(self) -> None:
        review_export = self.contract.get("review_export") or {}

        if self.contract_rel_path and review_export.get("include_contract", True):
            self.add(self.contract_rel_path, required=True, source="review_export.include_contract", artifact_type="contract")

        if review_export.get("include_folder_structure", True):
            folder_structure = dict_get(self.contract, "repository", "folder_structure_path")
            if folder_structure:
                self.add(folder_structure, required=True, source="review_export.include_folder_structure", artifact_type="documentation")

        if review_export.get("include_guardrail_scripts", True):
            for path in (
                "scripts/review_guardrails/stage_packager.py",
                "scripts/review_guardrails/review_export_validator.py",
                "scripts/review_guardrails/stage_completion_validator.py",
                "scripts/review_guardrails/stage_contract.schema.json",
            ):
                self.add(path, required=True, source="review_export.include_guardrail_scripts", artifact_type="script")

        for path in as_list(review_export.get("required_in_zip")):
            if isinstance(path, str):
                self.add(path, required=True, source="review_export.required_in_zip")

        listing_path = review_export.get("zip_listing_log_path")
        if listing_path:
            self.add(
                listing_path,
                required=True,
                source="review_export.zip_listing_log_path",
                artifact_type="log",
                generated_by_packager=True,
            )

    def _collect_global_files(self) -> None:
        for source_name in ("global_allowed_files",):
            file_set = self.contract.get(source_name) or {}
            for bucket, path in iter_file_set_paths(file_set):
                artifact_type = self._artifact_type_for_bucket(bucket)
                self.add(path, required=True, source=f"{source_name}.{bucket}", artifact_type=artifact_type)

    def _collect_stage_artifacts(self) -> None:
        for artifact in as_list(self.contract.get("required_stage_artifacts")):
            if not isinstance(artifact, Mapping):
                continue
            path = artifact.get("path")
            required = bool(artifact.get("required", True))
            artifact_type = artifact.get("artifact_type")
            if isinstance(path, str):
                self.add(path, required=required, source="required_stage_artifacts", artifact_type=artifact_type)

    def _collect_task_files(self) -> None:
        for task in as_list(self.contract.get("task_sequence")):
            if not isinstance(task, Mapping):
                continue
            task_id = task.get("task_id", "UNKNOWN_TASK")

            allowed_files = task.get("allowed_files") or {}
            for bucket, path in iter_file_set_paths(allowed_files):
                artifact_type = self._artifact_type_for_bucket(bucket)
                self.add(path, required=True, source=f"task:{task_id}:allowed_files.{bucket}", artifact_type=artifact_type)

            for artifact in as_list(task.get("expected_outputs")):
                if not isinstance(artifact, Mapping):
                    continue
                path = artifact.get("path")
                required = bool(artifact.get("required", True))
                artifact_type = artifact.get("artifact_type")
                if isinstance(path, str):
                    self.add(path, required=required, source=f"task:{task_id}:expected_outputs", artifact_type=artifact_type)

            for validator in as_list(task.get("validators")):
                if not isinstance(validator, Mapping):
                    continue
                for source_label, path in iter_validator_paths(validator):
                    self.add(path, required=True, source=f"task:{task_id}:{source_label}", artifact_type=self._artifact_type_for_validator(validator))

        preflight = self.contract.get("preflight") or {}
        for validator in as_list(preflight.get("checks")):
            if not isinstance(validator, Mapping):
                continue
            for source_label, path in iter_validator_paths(validator):
                self.add(path, required=True, source=f"preflight:{source_label}", artifact_type=self._artifact_type_for_validator(validator))

    def _collect_kimchi_updates(self) -> None:
        updates = self.contract.get("kimchi_updates") or {}

        for change in as_list(updates.get("changed_files")):
            if isinstance(change, Mapping) and isinstance(change.get("path"), str):
                self.add(change["path"], required=True, source="kimchi_updates.changed_files", artifact_type="source")

        for read_claim in as_list(updates.get("files_read_end_to_end")):
            if isinstance(read_claim, Mapping) and isinstance(read_claim.get("path"), str):
                self.add(read_claim["path"], required=True, source="kimchi_updates.files_read_end_to_end", artifact_type="source")

        for path in as_list(updates.get("evidence_created")):
            if isinstance(path, str):
                self.add(path, required=True, source="kimchi_updates.evidence_created", artifact_type="log")

        for path in as_list(updates.get("screenshots_created")):
            if isinstance(path, str):
                self.add(path, required=True, source="kimchi_updates.screenshots_created", artifact_type="screenshot")

        for command in as_list(updates.get("commands_run")):
            if isinstance(command, Mapping) and isinstance(command.get("evidence_log"), str):
                self.add(command["evidence_log"], required=True, source="kimchi_updates.commands_run.evidence_log", artifact_type="log")

        for blocker in as_list(updates.get("known_blockers")):
            if not isinstance(blocker, Mapping):
                continue
            for path in as_list(blocker.get("evidence")):
                if isinstance(path, str):
                    self.add(path, required=True, source="kimchi_updates.known_blockers.evidence", artifact_type="log")

    def _collect_metrics_files(self) -> None:
        metrics_path = dict_get(self.contract, "run_metrics", "path")
        if metrics_path:
            self.add(metrics_path, required=False, source="run_metrics.path", artifact_type="log")

        cost_metrics_path = dict_get(self.contract, "cost_control", "metrics_log_path")
        if cost_metrics_path:
            self.add(cost_metrics_path, required=False, source="cost_control.metrics_log_path", artifact_type="log")

    def _collect_generated_packager_files(self) -> None:
        contract_id = str(self.contract.get("contract_id") or "stage").replace("/", "_")
        report_path = f"tests/results/evidence/validator_outputs/{contract_id}_packager_report.json"
        self.add(
            report_path,
            required=True,
            source="stage_packager.generated_report",
            artifact_type="validator_output",
            generated_by_packager=True,
        )

    @staticmethod
    def _artifact_type_for_bucket(bucket: str) -> str:
        return {
            "read": "source",
            "edit": "source",
            "include_in_zip": "source",
            "evidence": "log",
            "screenshots": "screenshot",
        }.get(bucket, "source")

    @staticmethod
    def _artifact_type_for_validator(validator: Mapping[str, Any]) -> str:
        validator_type = str(validator.get("type") or "")
        if validator_type.startswith("log_") or validator_type in {"pytest_collected_tests", "curl_status_check", "command_exit_code"}:
            return "log"
        if validator_type.startswith("screenshot_"):
            return "screenshot"
        if validator_type.startswith("zip_") or validator_type == "ledger_matches_zip":
            return "manifest"
        return "source"


class ExclusionPolicy:
    """Centralized path exclusion and forbidden-entry policy."""

    def __init__(self, contract: Mapping[str, Any]) -> None:
        review_export = contract.get("review_export") or {}
        self.exclude_globs: List[str] = list(DEFAULT_EXCLUDE_GLOBS)
        self.exclude_globs.extend(str(item) for item in as_list(review_export.get("exclude_patterns")) if isinstance(item, str))

        self.forbidden_zip_patterns: List[re.Pattern[str]] = [re.compile(pattern) for pattern in DEFAULT_FORBIDDEN_ZIP_REGEX]
        self.forbidden_zip_patterns.extend(
            re.compile(str(item)) for item in as_list(review_export.get("forbidden_zip_entry_patterns")) if isinstance(item, str)
        )

        self.secret_globs: List[str] = list(DEFAULT_SECRET_GLOBS)

    def is_excluded(self, rel_path: str) -> bool:
        normalized = rel_path.replace("\\", "/")
        name = normalized.split("/")[-1]
        for pattern in self.exclude_globs:
            if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern):
                return True
        return False

    def is_secret_like(self, rel_path: str) -> bool:
        normalized = rel_path.replace("\\", "/")
        name = normalized.split("/")[-1]
        for pattern in self.secret_globs:
            if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern):
                return True
        return False

    def forbidden_zip_reasons(self, zip_entry: str) -> List[str]:
        return [pattern.pattern for pattern in self.forbidden_zip_patterns if pattern.search(zip_entry)]


class StagePackager:
    """Main packager orchestration."""

    def __init__(self, config: PackagerConfig) -> None:
        self.config = config
        self.repo_root = config.repo_root.resolve()
        self.contract_path = config.contract_path
        self.contract = load_json(self.contract_path)
        self.contract_rel_path = self._contract_rel_path()
        self.policy = ExclusionPolicy(self.contract)

        self.output_dir = safe_rel_to_path(self.repo_root, dict_get(self.contract, "review_export", "output_dir"))
        self.zip_path = safe_rel_to_path(self.repo_root, dict_get(self.contract, "review_export", "zip_path"))

        zip_listing = dict_get(self.contract, "review_export", "zip_listing_log_path")
        if not zip_listing:
            stage_id = str(dict_get(self.contract, "stage", "stage_id", default="stage")).lower()
            zip_listing = f"tests/results/evidence/logs/{stage_id}-zip-listing.log"
        self.zip_listing_log_path = safe_rel_to_path(self.repo_root, zip_listing)
        self.zip_listing_rel_path = normalize_rel_path(zip_listing)

        contract_id = str(self.contract.get("contract_id") or "stage").replace("/", "_")
        self.packager_report_rel_path = f"tests/results/evidence/validator_outputs/{contract_id}_packager_report.json"
        self.packager_report_path = safe_rel_to_path(self.repo_root, self.packager_report_rel_path)

        self.copy_records: List[CopyRecord] = []
        self.missing_required: List[Dict[str, Any]] = []
        self.missing_optional: List[Dict[str, Any]] = []
        self.forbidden_paths: List[Dict[str, Any]] = []
        self.copy_errors: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.copied_rel_paths: Set[str] = set()
        self.skipped_rel_paths: Set[str] = set()

    def _contract_rel_path(self) -> Optional[str]:
        try:
            return self.contract_path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return None

    def run(self) -> Tuple[str, Dict[str, Any]]:
        self.warnings.extend(validate_repo_root(self.repo_root, self.contract))
        requirements = ContractPathCollector(self.contract, self.contract_rel_path).collect()

        self._prepare_output_dir()
        self._copy_requirements(requirements)

        # Generated outputs must be materialized before final zipping.
        planned_entries = self._planned_export_entries(extra_rel_paths=[self.zip_listing_rel_path, self.packager_report_rel_path])
        self._write_zip_listing_log(planned_entries)
        self._copy_generated_file(self.zip_listing_rel_path, self.zip_listing_log_path)

        preliminary_status = self._derive_status()
        preliminary_report = self._build_report(preliminary_status, planned_entries)
        write_json(self.packager_report_path, preliminary_report)
        self._copy_generated_file(self.packager_report_rel_path, self.packager_report_path)

        if not self.config.dry_run:
            zip_entries = self._create_zip()
        else:
            zip_entries = planned_entries

        final_status = self._derive_status(zip_entries)
        final_report = self._build_report(final_status, zip_entries)

        # Update report with final zip entries and rebuild so the zip includes the final report.
        write_json(self.packager_report_path, final_report)
        self._copy_generated_file(self.packager_report_rel_path, self.packager_report_path)
        if not self.config.dry_run:
            zip_entries = self._create_zip()
            final_report = self._build_report(self._derive_status(zip_entries), zip_entries)
            write_json(self.packager_report_path, final_report)
            self._copy_generated_file(self.packager_report_rel_path, self.packager_report_path)
            zip_entries = self._create_zip()
            final_report = self._build_report(self._derive_status(zip_entries), zip_entries)

        return final_report["status"], final_report

    def _prepare_output_dir(self) -> None:
        if self.output_dir == self.repo_root:
            raise PackagerError("review_export.output_dir cannot be the repo root")
        if self.config.clean_output_dir and self.output_dir.exists():
            if self.config.verbose:
                print(f"Cleaning output directory: {self.output_dir}")
            if not self.config.dry_run:
                shutil.rmtree(self.output_dir)
        if not self.config.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.zip_path.parent.mkdir(parents=True, exist_ok=True)

    def _copy_requirements(self, requirements: Mapping[str, FileRequirement]) -> None:
        for rel_path, requirement in requirements.items():
            self._copy_requirement(requirement)

    def _copy_requirement(self, requirement: FileRequirement) -> None:
        rel_path = requirement.path

        if rel_path in {dict_get(self.contract, "review_export", "zip_path"), dict_get(self.contract, "review_export", "output_dir")}:
            self._record_skip(requirement, "skipped-self-reference")
            return

        if self.policy.is_secret_like(rel_path):
            self._record_forbidden(requirement, "secret-like path is not allowed in review export")
            return

        if self.policy.is_excluded(rel_path) and not requirement.generated_by_packager:
            self._record_skip(requirement, "excluded-by-pattern")
            return

        source_path = safe_rel_to_path(self.repo_root, rel_path)

        if requirement.generated_by_packager:
            # Generated files are written later and then copied.
            if not source_path.exists():
                self._record_skip(requirement, "generated-by-packager-pending")
                return

        if not source_path.exists():
            record = {
                "path": rel_path,
                "required": requirement.required,
                "sources": sorted(requirement.sources),
                "artifact_types": sorted(requirement.artifact_types),
                "reason": "missing-in-repo",
            }
            if requirement.required:
                self.missing_required.append(record)
            else:
                self.missing_optional.append(record)
            self.copy_records.append(
                CopyRecord(
                    path=rel_path,
                    status="missing",
                    reason="missing-in-repo",
                    required=requirement.required,
                    sources=sorted(requirement.sources),
                    artifact_types=sorted(requirement.artifact_types),
                )
            )
            return

        if source_path.is_dir():
            self._copy_directory(requirement, source_path)
            return

        self._copy_file(requirement, source_path)

    def _copy_file(self, requirement: FileRequirement, source_path: Path) -> None:
        rel_path = requirement.path
        target_path = safe_rel_to_path(self.output_dir, rel_path)
        try:
            byte_count = source_path.stat().st_size
            if not self.config.dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
            self.copied_rel_paths.add(rel_path)
            self.copy_records.append(
                CopyRecord(
                    path=rel_path,
                    status="copied",
                    reason="ok",
                    required=requirement.required,
                    sources=sorted(requirement.sources),
                    artifact_types=sorted(requirement.artifact_types),
                    bytes_copied=byte_count,
                )
            )
        except OSError as exc:
            self.copy_errors.append({"path": rel_path, "error": str(exc)})
            self.copy_records.append(
                CopyRecord(
                    path=rel_path,
                    status="copy-error",
                    reason=str(exc),
                    required=requirement.required,
                    sources=sorted(requirement.sources),
                    artifact_types=sorted(requirement.artifact_types),
                )
            )

    def _copy_directory(self, requirement: FileRequirement, source_path: Path) -> None:
        rel_root = requirement.path
        copied_count = 0
        for child in sorted(source_path.rglob("*")):
            if child.is_dir():
                continue
            try:
                rel_child = child.resolve().relative_to(self.repo_root).as_posix()
            except ValueError:
                continue
            child_requirement = FileRequirement(
                path=rel_child,
                required=requirement.required,
                sources=set(requirement.sources) | {f"directory:{rel_root}"},
                artifact_types=set(requirement.artifact_types),
            )
            if self.policy.is_secret_like(rel_child):
                self._record_forbidden(child_requirement, "secret-like path is not allowed in review export")
                continue
            if self.policy.is_excluded(rel_child):
                self._record_skip(child_requirement, "excluded-by-pattern")
                continue
            self._copy_file(child_requirement, child)
            copied_count += 1
        if copied_count == 0 and requirement.required:
            self.warnings.append(f"Required directory had no copyable files: {rel_root}")

    def _record_skip(self, requirement: FileRequirement, reason: str) -> None:
        self.skipped_rel_paths.add(requirement.path)
        self.copy_records.append(
            CopyRecord(
                path=requirement.path,
                status="skipped",
                reason=reason,
                required=requirement.required,
                sources=sorted(requirement.sources),
                artifact_types=sorted(requirement.artifact_types),
            )
        )

    def _record_forbidden(self, requirement: FileRequirement, reason: str) -> None:
        self.forbidden_paths.append(
            {
                "path": requirement.path,
                "required": requirement.required,
                "sources": sorted(requirement.sources),
                "artifact_types": sorted(requirement.artifact_types),
                "reason": reason,
            }
        )
        self.copy_records.append(
            CopyRecord(
                path=requirement.path,
                status="forbidden",
                reason=reason,
                required=requirement.required,
                sources=sorted(requirement.sources),
                artifact_types=sorted(requirement.artifact_types),
            )
        )

    def _copy_generated_file(self, rel_path: str, source_path: Path) -> None:
        requirement = FileRequirement(
            path=normalize_rel_path(rel_path),
            required=True,
            sources={"stage_packager.generated"},
            artifact_types={"validator_output" if rel_path.endswith(".json") else "log"},
            generated_by_packager=True,
        )
        if source_path.exists():
            self._copy_file(requirement, source_path)

    def _planned_export_entries(self, *, extra_rel_paths: Optional[Sequence[str]] = None) -> List[str]:
        entries: Set[str] = set()
        if self.output_dir.exists():
            for path in self.output_dir.rglob("*"):
                if path.is_file():
                    rel = path.relative_to(self.output_dir).as_posix()
                    if not self.policy.is_excluded(rel):
                        entries.add(rel)
        for extra in extra_rel_paths or []:
            entries.add(normalize_rel_path(extra))
        return sorted(entries)

    def _write_zip_listing_log(self, entries: Sequence[str]) -> None:
        lines = [
            f"Archive: {dict_get(self.contract, 'review_export', 'zip_path')}",
            f"Generated by: stage_packager.py",
            f"Generated at UTC: {utc_now_iso()}",
            "",
            "Length      Name",
            "----------  ----",
        ]
        total = 0
        for entry in sorted(entries):
            source_in_export = self.output_dir / entry
            source_in_repo = self.repo_root / entry
            if source_in_export.exists() and source_in_export.is_file():
                size = source_in_export.stat().st_size
            elif source_in_repo.exists() and source_in_repo.is_file():
                size = source_in_repo.stat().st_size
            else:
                size = 0
            total += size
            lines.append(f"{size:10d}  {entry}")
        lines.extend([
            "----------  ----",
            f"{total:10d}  {len(entries)} files",
            "",
        ])
        if not self.config.dry_run:
            self.zip_listing_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.zip_listing_log_path.write_text("\n".join(lines), encoding="utf-8")

    def _create_zip(self) -> List[str]:
        if self.zip_path.exists():
            self.zip_path.unlink()

        entries: List[str] = []
        with zipfile.ZipFile(self.zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(self.output_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(self.output_dir).as_posix()
                if self.policy.is_excluded(rel):
                    continue
                forbidden = self.policy.forbidden_zip_reasons(rel)
                if forbidden:
                    self.forbidden_paths.append(
                        {
                            "path": rel,
                            "required": True,
                            "sources": ["zip-entry"],
                            "artifact_types": ["zip"],
                            "reason": f"forbidden zip entry pattern(s): {forbidden}",
                        }
                    )
                    continue
                zf.write(path, arcname=rel)
                entries.append(rel)
        return sorted(entries)

    def _derive_status(self, zip_entries: Optional[Sequence[str]] = None) -> str:
        if self.missing_required or self.forbidden_paths or self.copy_errors:
            return STATUS_NO_GO
        if self.missing_optional or self.warnings:
            return STATUS_PARTIAL
        if zip_entries is not None:
            if self._zip_has_forbidden_entries(zip_entries):
                return STATUS_NO_GO
        return STATUS_PASS

    def _zip_has_forbidden_entries(self, zip_entries: Sequence[str]) -> bool:
        return any(self.policy.forbidden_zip_reasons(entry) for entry in zip_entries)

    def _build_report(self, status: str, zip_entries: Sequence[str]) -> Dict[str, Any]:
        contract_id = self.contract.get("contract_id")
        stage = self.contract.get("stage") or {}
        review_export = self.contract.get("review_export") or {}

        category_counts = self._category_counts(zip_entries)
        required_in_zip = set(str(p) for p in as_list(review_export.get("required_in_zip")) if isinstance(p, str))
        zip_entry_set = set(zip_entries)
        required_missing_from_zip = sorted(
            path for path in required_in_zip if path not in zip_entry_set and not self.policy.is_excluded(path)
        )

        if required_missing_from_zip and status == STATUS_PASS:
            status = STATUS_NO_GO

        next_action = self._next_action(status, required_missing_from_zip)

        return {
            "generated_by": "stage_packager.py",
            "generated_at": utc_now_iso(),
            "status": status,
            "contract_id": contract_id,
            "stage_id": stage.get("stage_id"),
            "stage_title": stage.get("stage_title"),
            "repo_root": str(self.repo_root),
            "contract_path": self.contract_rel_path or str(self.contract_path),
            "review_export": {
                "output_dir": review_export.get("output_dir"),
                "zip_path": review_export.get("zip_path"),
                "zip_listing_log_path": self.zip_listing_rel_path,
                "packager_report_path": self.packager_report_rel_path,
                "preserve_repo_relative_paths": review_export.get("preserve_repo_relative_paths"),
                "copy_missing_expected_files": review_export.get("copy_missing_expected_files"),
                "fail_if_repo_file_missing": review_export.get("fail_if_repo_file_missing"),
            },
            "counts": {
                "copy_records": len(self.copy_records),
                "copied_files": len([r for r in self.copy_records if r.status == "copied"]),
                "skipped_files": len([r for r in self.copy_records if r.status == "skipped"]),
                "missing_required": len(self.missing_required),
                "missing_optional": len(self.missing_optional),
                "forbidden_paths": len(self.forbidden_paths),
                "copy_errors": len(self.copy_errors),
                "zip_entries": len(zip_entries),
                "zip_category_counts": category_counts,
            },
            "zip_entries": list(zip_entries),
            "required_missing_from_zip": required_missing_from_zip,
            "missing_required": self.missing_required,
            "missing_optional": self.missing_optional,
            "forbidden_paths": self.forbidden_paths,
            "copy_errors": self.copy_errors,
            "warnings": self.warnings,
            "copy_records": [dataclasses.asdict(record) for record in self.copy_records],
            "next_action": next_action,
        }

    @staticmethod
    def _category_counts(entries: Sequence[str]) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for entry in entries:
            if entry.startswith("services/"):
                counts["backend"] += 1
            elif entry.startswith("apps/"):
                counts["frontend"] += 1
            elif entry.startswith("tests/"):
                counts["tests_or_evidence"] += 1
            elif entry.startswith("scripts/"):
                counts["scripts"] += 1
            elif entry.startswith("docs/"):
                counts["docs"] += 1
            elif entry.startswith("review_contracts/"):
                counts["contract"] += 1
            elif entry.startswith("packages/"):
                counts["packages"] += 1
            else:
                counts["other"] += 1
        return dict(sorted(counts.items()))

    def _next_action(self, status: str, required_missing_from_zip: Sequence[str]) -> Dict[str, Any]:
        if status == STATUS_PASS:
            return {
                "action_type": "manual_review",
                "title": "Proceed to manual source-grounded review",
                "instructions": [
                    "Review changed source/config/test files end-to-end.",
                    "Review relevant unchanged source/config files included in the zip.",
                    "Review evidence logs and screenshots.",
                    "Do not accept from packager status alone.",
                ],
            }

        instructions: List[str] = []
        if self.missing_required:
            instructions.append("Create or restore missing required repo files, or update the contract only if the file is truly not required.")
        if self.forbidden_paths:
            instructions.append("Remove forbidden/secret/generated paths from the contract or export; do not package secrets or build artifacts.")
        if self.copy_errors:
            instructions.append("Fix copy errors shown in packager report.")
        if required_missing_from_zip:
            instructions.append("Ensure required_in_zip files are copied and present in final zip with exact repo-relative paths.")
        if self.warnings:
            instructions.append("Review warnings and either fix them or document explicit defer/partial status.")

        return {
            "action_type": "fix_packaging",
            "title": "Fix review-export packaging before implementation review",
            "instructions": instructions or ["Inspect packager report and fix packaging status."],
        }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package BhojanGo stage review export from a stage contract JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--contract",
        required=True,
        help="Repo-relative or absolute path to stage contract JSON.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repo root. Defaults to nearest parent containing package.json and pnpm-workspace.yaml, otherwise current working directory.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete review_export.output_dir before copying files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without copying or creating zip.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress.",
    )
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> PackagerConfig:
    start = Path.cwd()
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else infer_repo_root(start)

    contract_arg = Path(args.contract).expanduser()
    if contract_arg.is_absolute():
        contract_path = contract_arg.resolve()
    else:
        contract_path = (repo_root / contract_arg).resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        raise PackagerError(f"Repo root is not a directory: {repo_root}")
    if not contract_path.exists() or not contract_path.is_file():
        raise PackagerError(f"Contract file is not found: {contract_path}")

    return PackagerConfig(
        repo_root=repo_root,
        contract_path=contract_path,
        clean_output_dir=bool(args.clean),
        dry_run=bool(args.dry_run),
        verbose=bool(args.verbose),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        config = resolve_paths(args)
        packager = StagePackager(config)
        status, report = packager.run()

        summary = {
            "status": status,
            "contract_id": report.get("contract_id"),
            "stage_id": report.get("stage_id"),
            "zip_path": report.get("review_export", {}).get("zip_path"),
            "packager_report_path": report.get("review_export", {}).get("packager_report_path"),
            "zip_entries": report.get("counts", {}).get("zip_entries"),
            "missing_required": report.get("counts", {}).get("missing_required"),
            "forbidden_paths": report.get("counts", {}).get("forbidden_paths"),
            "copy_errors": report.get("counts", {}).get("copy_errors"),
            "next_action": report.get("next_action", {}).get("title"),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        return 0 if status == STATUS_PASS else 1

    except PackagerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: interrupted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
