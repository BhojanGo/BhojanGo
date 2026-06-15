#!/usr/bin/env python3
"""
review_export_validator.py

Independent review-export validator for BhojanGo stage closure zips.

Purpose
-------
This script validates the review zip/export created by stage_packager.py against
a stage contract JSON. It is deliberately mechanical. It does not decide product
quality and does not replace manual code review. It prevents common closure
failures before manual review begins:

- missing review zip
- zip paths not repo-relative
- flattened "changed/" or "reference/" folders
- __MACOSX/.DS_Store/build artifacts
- required source/config/test/evidence files missing from zip
- files claimed by the ledger but missing from zip
- screenshots/logs/evidence files absent or empty
- required file categories missing
- zip-listing log missing
- guardrail/contract/folder-structure files missing

The validator also emits a deterministic next_action block so Kimchi knows the
smallest correction to perform instead of drifting into broad repo work.

Typical usage
-------------
From repo root:

    python scripts/review_guardrails/review_export_validator.py \
      --contract review_contracts/SPR-02-v3.contract.json

Optional:

    python scripts/review_guardrails/review_export_validator.py \
      --repo-root /path/to/BhojanGo \
      --contract review_contracts/SPR-02-v3.contract.json \
      --zip review_exports/SPR-02_scope_review_v3.zip

Exit codes
----------
0 = review export mechanically PASS
1 = review export PARTIAL or NO-GO
2 = invalid arguments / unreadable contract / unreadable zip
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import json
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL"
STATUS_NO_GO = "NO-GO"

DEFAULT_REPO_MARKERS = ("package.json", "pnpm-workspace.yaml")

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
    r"(^|/)tmp(/|$)",
)

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

TEXT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".log",
    ".toml", ".yml", ".yaml", ".sql", ".sh", ".ini", ".cfg", ".mjs",
    ".css", ".html", ".csv"
}

SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class ValidatorError(Exception):
    """Fatal validator setup/runtime error."""


@dataclasses.dataclass
class ExpectedFile:
    path: str
    required: bool = True
    sources: Set[str] = dataclasses.field(default_factory=set)
    artifact_types: Set[str] = dataclasses.field(default_factory=set)

    def merge(self, *, required: bool, source: str, artifact_type: Optional[str] = None) -> None:
        self.required = self.required or required
        self.sources.add(source)
        if artifact_type:
            self.artifact_types.add(artifact_type)


@dataclasses.dataclass
class ValidationFinding:
    code: str
    severity: str
    path: Optional[str]
    message: str
    repair_instruction: str
    task_id: Optional[str] = None
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ValidatorConfig:
    repo_root: Path
    contract_path: Path
    zip_override: Optional[Path] = None
    report_out: Optional[Path] = None
    verbose: bool = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidatorError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidatorError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def is_relative_repo_path(raw: str) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    value = raw.replace("\\", "/")
    if value.startswith("/") or value.startswith("./"):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    if any(part == ".." for part in value.split("/")):
        return False
    return True


def normalize_rel_path(raw: str) -> str:
    value = raw.replace("\\", "/").strip()
    while "//" in value:
        value = value.replace("//", "/")
    value = value.rstrip("/")
    if not is_relative_repo_path(value):
        raise ValidatorError(f"Invalid repo-relative path: {raw!r}")
    return value


def safe_rel_to_path(repo_root: Path, rel_path: str) -> Path:
    rel = normalize_rel_path(rel_path)
    candidate = (repo_root / rel).resolve()
    root = repo_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidatorError(f"Path escapes repo root: {rel_path}") from exc
    return candidate


def infer_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if all((candidate / marker).exists() for marker in DEFAULT_REPO_MARKERS):
            return candidate
    return current


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def truthy_text(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "included", "in_zip", "pass", "present"}


def detect_category(path: str) -> str:
    if path.startswith("services/"):
        return "backend"
    if path.startswith("apps/"):
        return "frontend"
    if path.startswith("tests/"):
        if "/screenshots/" in path:
            return "screenshots"
        if "/logs/" in path or "/evidence/" in path or "/results/" in path:
            return "evidence"
        return "tests"
    if path.startswith("scripts/review_guardrails/"):
        return "validators"
    if path.startswith("scripts/"):
        return "scripts"
    if path.startswith("docs/"):
        return "docs"
    if path.startswith("review_contracts/"):
        return "contract"
    if path.startswith("packages/"):
        return "packages"
    if path.endswith(".json") and "contract" in path:
        return "contract"
    return "other"


def artifact_type_from_path(path: str) -> str:
    lower = path.lower()
    suffix = Path(lower).suffix
    if suffix in SCREENSHOT_EXTENSIONS:
        return "screenshot"
    if lower.endswith(".log") or "/logs/" in lower:
        return "log"
    if lower.endswith(".md") and ("manifest" in lower or "ledger" in lower or "summary" in lower):
        return "manifest"
    if lower.endswith(".json") and "contract" in lower:
        return "contract"
    if lower.endswith(".py") and "scripts/review_guardrails" in lower:
        return "script"
    if lower.startswith("services/"):
        return "source"
    if lower.startswith("apps/"):
        return "source"
    if lower.startswith("tests/backend/") or lower.startswith("tests/frontend/"):
        return "test"
    if suffix in {".toml", ".yml", ".yaml", ".json", ".mjs"}:
        return "config"
    return "source"


def iter_file_set_paths(file_set: Optional[Mapping[str, Any]]) -> Iterable[Tuple[str, str]]:
    if not isinstance(file_set, Mapping):
        return
    for bucket in ("read", "edit", "include_in_zip", "evidence", "screenshots"):
        for path in as_list(file_set.get(bucket)):
            if isinstance(path, str):
                yield bucket, path


def iter_validator_paths(validator: Mapping[str, Any]) -> Iterable[Tuple[str, str]]:
    if not isinstance(validator, Mapping):
        return
    validator_type = str(validator.get("type") or "")
    if isinstance(validator.get("path"), str):
        if validator_type not in {"file_not_exists", "zip_not_contains", "code_regex_not_exists"}:
            yield f"validator:{validator.get('validator_id', 'unknown')}:path", validator["path"]
    if isinstance(validator.get("paths"), list):
        for path in validator["paths"]:
            if isinstance(path, str):
                yield f"validator:{validator.get('validator_id', 'unknown')}:paths", path
    if isinstance(validator.get("zip_path"), str):
        yield f"validator:{validator.get('validator_id', 'unknown')}:zip_path", validator["zip_path"]


class ContractExpectedFileCollector:
    """Collect expected file paths from the stage contract."""

    def __init__(self, contract: Mapping[str, Any], contract_rel_path: Optional[str]) -> None:
        self.contract = contract
        self.contract_rel_path = contract_rel_path
        self.expected: Dict[str, ExpectedFile] = {}

    def add(self, raw_path: Optional[str], *, required: bool, source: str, artifact_type: Optional[str] = None) -> None:
        if not raw_path or not isinstance(raw_path, str):
            return
        rel_path = normalize_rel_path(raw_path)
        existing = self.expected.get(rel_path)
        if existing is None:
            self.expected[rel_path] = ExpectedFile(
                path=rel_path,
                required=required,
                sources={source},
                artifact_types=set([artifact_type]) if artifact_type else set(),
            )
        else:
            existing.merge(required=required, source=source, artifact_type=artifact_type)

    def collect(self) -> Dict[str, ExpectedFile]:
        self._collect_repository()
        self._collect_review_export()
        self._collect_global_files()
        self._collect_stage_artifacts()
        self._collect_tasks()
        self._collect_kimchi_updates()
        self._collect_metrics()
        return dict(sorted(self.expected.items(), key=lambda item: item[0]))

    def _collect_repository(self) -> None:
        repo = self.contract.get("repository") or {}
        if isinstance(repo.get("folder_structure_path"), str):
            self.add(repo["folder_structure_path"], required=True, source="repository.folder_structure_path", artifact_type="documentation")
        for path in as_list(repo.get("source_of_truth_files")):
            if isinstance(path, str):
                self.add(path, required=True, source="repository.source_of_truth_files", artifact_type=artifact_type_from_path(path))
        for marker in as_list(repo.get("repo_markers")):
            if isinstance(marker, str):
                self.add(marker, required=True, source="repository.repo_markers", artifact_type=artifact_type_from_path(marker))

    def _collect_review_export(self) -> None:
        review_export = self.contract.get("review_export") or {}
        if review_export.get("include_contract", True) and self.contract_rel_path:
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
                self.add(path, required=True, source="review_export.required_in_zip", artifact_type=artifact_type_from_path(path))

        zip_listing = review_export.get("zip_listing_log_path")
        if isinstance(zip_listing, str):
            self.add(zip_listing, required=True, source="review_export.zip_listing_log_path", artifact_type="log")

    def _collect_global_files(self) -> None:
        for bucket, path in iter_file_set_paths(self.contract.get("global_allowed_files") or {}):
            self.add(path, required=True, source=f"global_allowed_files.{bucket}", artifact_type=artifact_type_from_path(path))

    def _collect_stage_artifacts(self) -> None:
        for artifact in as_list(self.contract.get("required_stage_artifacts")):
            if isinstance(artifact, Mapping) and isinstance(artifact.get("path"), str):
                self.add(
                    artifact["path"],
                    required=bool(artifact.get("required", True)),
                    source="required_stage_artifacts",
                    artifact_type=str(artifact.get("artifact_type") or artifact_type_from_path(artifact["path"])),
                )

    def _collect_tasks(self) -> None:
        for task in as_list(self.contract.get("task_sequence")):
            if not isinstance(task, Mapping):
                continue
            task_id = str(task.get("task_id") or "UNKNOWN_TASK")
            for bucket, path in iter_file_set_paths(task.get("allowed_files") or {}):
                self.add(path, required=True, source=f"task:{task_id}:allowed_files.{bucket}", artifact_type=artifact_type_from_path(path))
            for artifact in as_list(task.get("expected_outputs")):
                if isinstance(artifact, Mapping) and isinstance(artifact.get("path"), str):
                    self.add(
                        artifact["path"],
                        required=bool(artifact.get("required", True)),
                        source=f"task:{task_id}:expected_outputs",
                        artifact_type=str(artifact.get("artifact_type") or artifact_type_from_path(artifact["path"])),
                    )
            for validator in as_list(task.get("validators")):
                if isinstance(validator, Mapping):
                    for source, path in iter_validator_paths(validator):
                        self.add(path, required=True, source=f"task:{task_id}:{source}", artifact_type=artifact_type_from_path(path))

        preflight = self.contract.get("preflight") or {}
        for validator in as_list(preflight.get("checks")):
            if isinstance(validator, Mapping):
                for source, path in iter_validator_paths(validator):
                    self.add(path, required=True, source=f"preflight:{source}", artifact_type=artifact_type_from_path(path))

    def _collect_kimchi_updates(self) -> None:
        updates = self.contract.get("kimchi_updates") or {}
        for change in as_list(updates.get("changed_files")):
            if isinstance(change, Mapping) and isinstance(change.get("path"), str):
                self.add(change["path"], required=True, source="kimchi_updates.changed_files", artifact_type=artifact_type_from_path(change["path"]))
        for claim in as_list(updates.get("files_read_end_to_end")):
            if isinstance(claim, Mapping) and isinstance(claim.get("path"), str):
                self.add(claim["path"], required=True, source="kimchi_updates.files_read_end_to_end", artifact_type=artifact_type_from_path(claim["path"]))
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
            if isinstance(blocker, Mapping):
                for path in as_list(blocker.get("evidence")):
                    if isinstance(path, str):
                        self.add(path, required=True, source="kimchi_updates.known_blockers.evidence", artifact_type=artifact_type_from_path(path))

    def _collect_metrics(self) -> None:
        for key_path in (("run_metrics", "path"), ("cost_control", "metrics_log_path")):
            path = dict_get(self.contract, *key_path)
            if isinstance(path, str):
                self.add(path, required=False, source=".".join(key_path), artifact_type="log")


class ZipSnapshot:
    """Read-only snapshot of a review zip."""

    def __init__(self, zip_path: Path) -> None:
        self.zip_path = zip_path
        self.entries: Dict[str, zipfile.ZipInfo] = {}
        self.directories: Set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.zip_path.exists():
            raise ValidatorError(f"Review zip not found: {self.zip_path}")
        if not self.zip_path.is_file():
            raise ValidatorError(f"Review zip path is not a file: {self.zip_path}")
        try:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                for info in zf.infolist():
                    name = info.filename.replace("\\", "/")
                    if name.endswith("/"):
                        self.directories.add(name.rstrip("/"))
                    else:
                        self.entries[name] = info
        except zipfile.BadZipFile as exc:
            raise ValidatorError(f"Invalid zip file: {self.zip_path}") from exc

    def has(self, rel_path: str) -> bool:
        rel = normalize_rel_path(rel_path)
        if rel in self.entries:
            return True
        prefix = rel.rstrip("/") + "/"
        return any(entry.startswith(prefix) for entry in self.entries)

    def size(self, rel_path: str) -> int:
        rel = normalize_rel_path(rel_path)
        info = self.entries.get(rel)
        return int(info.file_size) if info else 0

    def read_text(self, rel_path: str, max_bytes: int = 5_000_000) -> str:
        rel = normalize_rel_path(rel_path)
        info = self.entries.get(rel)
        if info is None:
            raise KeyError(rel)
        if info.file_size > max_bytes:
            raise ValueError(f"File too large to read as text: {rel} ({info.file_size} bytes)")
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            raw = zf.read(info)
        return raw.decode("utf-8", errors="replace")

    def read_bytes(self, rel_path: str, max_bytes: int = 5_000_000) -> bytes:
        rel = normalize_rel_path(rel_path)
        info = self.entries.get(rel)
        if info is None:
            raise KeyError(rel)
        if info.file_size > max_bytes:
            raise ValueError(f"File too large to read: {rel} ({info.file_size} bytes)")
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            return zf.read(info)


class LedgerParser:
    """Parse file-read ledgers from JSON or Markdown."""

    def __init__(self, zip_snapshot: ZipSnapshot) -> None:
        self.zip = zip_snapshot

    def find_ledger_paths(self) -> List[str]:
        candidates = []
        for entry in self.zip.entries:
            lower = entry.lower()
            if "file-read-ledger" in lower or "file_read_ledger" in lower:
                candidates.append(entry)
        return sorted(candidates)

    def parse_all(self) -> Dict[str, Dict[str, Any]]:
        claims: Dict[str, Dict[str, Any]] = {}
        for ledger_path in self.find_ledger_paths():
            suffix = Path(ledger_path).suffix.lower()
            try:
                if suffix == ".json":
                    content = json.loads(self.zip.read_text(ledger_path))
                    claims.update(self._parse_json_ledger(content, ledger_path))
                else:
                    text = self.zip.read_text(ledger_path)
                    claims.update(self._parse_markdown_ledger(text, ledger_path))
            except Exception as exc:  # intentionally captured as validation finding later
                claims[f"__PARSER_ERROR__:{ledger_path}"] = {
                    "path": ledger_path,
                    "ledger_path": ledger_path,
                    "parser_error": str(exc),
                    "included_in_zip": None,
                }
        return claims

    def _parse_json_ledger(self, node: Any, ledger_path: str) -> Dict[str, Dict[str, Any]]:
        records: Dict[str, Dict[str, Any]] = {}

        def walk(value: Any) -> None:
            if isinstance(value, Mapping):
                path_value = value.get("path") or value.get("file_path") or value.get("file")
                if isinstance(path_value, str) and is_relative_repo_path(path_value):
                    included = self._extract_included_value(value)
                    read_e2e = self._extract_read_value(value)
                    records[normalize_rel_path(path_value)] = {
                        "path": normalize_rel_path(path_value),
                        "ledger_path": ledger_path,
                        "included_in_zip": included,
                        "read_end_to_end": read_e2e,
                        "raw": dict(value),
                    }
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(node)
        return records

    def _parse_markdown_ledger(self, text: str, ledger_path: str) -> Dict[str, Dict[str, Any]]:
        records: Dict[str, Dict[str, Any]] = {}
        header: Optional[List[str]] = None
        for line in text.splitlines():
            if "|" not in line:
                continue
            cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            normalized = [normalize_header(cell) for cell in cells]
            if any("path" == cell or "file_path" == cell or cell == "file" for cell in normalized):
                header = normalized
                continue
            if set("".join(cells).replace(" ", "")) <= {"-", ":"}:
                continue
            if not header or len(cells) != len(header):
                # Fallback: extract first repo-like path and detect included/read booleans in line.
                found = self._extract_paths_from_text(line)
                for path in found:
                    records[path] = {
                        "path": path,
                        "ledger_path": ledger_path,
                        "included_in_zip": self._line_has_yes_for(line, ["included", "zip", "in zip"]),
                        "read_end_to_end": self._line_has_yes_for(line, ["read", "end-to-end", "end_to_end"]),
                        "raw_line": line,
                    }
                continue

            row = dict(zip(header, cells))
            path = self._extract_path_from_row(row)
            if not path:
                continue
            included = self._extract_included_from_row(row)
            read_e2e = self._extract_read_from_row(row)
            records[path] = {
                "path": path,
                "ledger_path": ledger_path,
                "included_in_zip": included,
                "read_end_to_end": read_e2e,
                "raw_row": row,
            }
        return records

    @staticmethod
    def _extract_included_value(row: Mapping[str, Any]) -> Optional[bool]:
        for key, value in row.items():
            key_norm = normalize_header(str(key))
            if "included" in key_norm and "zip" in key_norm:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return truthy_text(value)
        return None

    @staticmethod
    def _extract_read_value(row: Mapping[str, Any]) -> Optional[bool]:
        for key, value in row.items():
            key_norm = normalize_header(str(key))
            if "read" in key_norm and ("end" in key_norm or "e2e" in key_norm):
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return truthy_text(value)
        return None

    @staticmethod
    def _extract_path_from_row(row: Mapping[str, str]) -> Optional[str]:
        for key, value in row.items():
            if key in {"path", "file_path", "file"} or "path" in key:
                candidate = value.strip().strip("`")
                if is_relative_repo_path(candidate):
                    return normalize_rel_path(candidate)
        return None

    @staticmethod
    def _extract_included_from_row(row: Mapping[str, str]) -> Optional[bool]:
        for key, value in row.items():
            if "included" in key and "zip" in key:
                return truthy_text(value)
            if key in {"in_zip", "zip"}:
                return truthy_text(value)
        return None

    @staticmethod
    def _extract_read_from_row(row: Mapping[str, str]) -> Optional[bool]:
        for key, value in row.items():
            if "read" in key and ("end" in key or "e2e" in key):
                return truthy_text(value)
        return None

    @staticmethod
    def _extract_paths_from_text(line: str) -> List[str]:
        # Conservative repo-like paths used in BhojanGo contracts.
        matches = re.findall(
            r"(?:services|apps|tests|scripts|docs|review_contracts|packages|infra)/[A-Za-z0-9_./()\[\]\-]+",
            line,
        )
        return [normalize_rel_path(match.strip("`|,")) for match in matches if is_relative_repo_path(match.strip("`|,"))]

    @staticmethod
    def _line_has_yes_for(line: str, keywords: Sequence[str]) -> Optional[bool]:
        lower = line.lower()
        if not any(keyword in lower for keyword in keywords):
            return None
        return bool(re.search(r"\b(yes|true|included|pass|present)\b", lower))


class ReviewExportValidator:
    """Main review-export validation orchestration."""

    def __init__(self, config: ValidatorConfig) -> None:
        self.config = config
        self.repo_root = config.repo_root.resolve()
        self.contract_path = config.contract_path
        self.contract = load_json(config.contract_path)
        self.contract_rel_path = self._contract_rel_path()
        self.zip_path = config.zip_override or safe_rel_to_path(self.repo_root, dict_get(self.contract, "review_export", "zip_path"))
        self.report_out = config.report_out or self._default_report_out()

        self.exclude_globs = list(DEFAULT_EXCLUDE_GLOBS)
        self.exclude_globs.extend(
            str(item) for item in as_list(dict_get(self.contract, "review_export", "exclude_patterns")) if isinstance(item, str)
        )

        self.forbidden_patterns = [re.compile(p) for p in DEFAULT_FORBIDDEN_ZIP_REGEX]
        self.forbidden_patterns.extend(
            re.compile(str(item))
            for item in as_list(dict_get(self.contract, "review_export", "forbidden_zip_entry_patterns"))
            if isinstance(item, str)
        )

        self.secret_globs = list(DEFAULT_SECRET_GLOBS)
        self.findings: List[ValidationFinding] = []
        self.warnings: List[ValidationFinding] = []

    def _contract_rel_path(self) -> Optional[str]:
        try:
            return self.contract_path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return None

    def _default_report_out(self) -> Path:
        contract_id = str(self.contract.get("contract_id") or "stage").replace("/", "_")
        return safe_rel_to_path(
            self.repo_root,
            f"tests/results/evidence/validator_outputs/{contract_id}_review_export_validation.json",
        )

    def validate(self) -> Tuple[str, Dict[str, Any]]:
        expected_files = ContractExpectedFileCollector(self.contract, self.contract_rel_path).collect()

        repo_root_findings = self._validate_repo_root()
        self.findings.extend(repo_root_findings)

        try:
            zip_snapshot = ZipSnapshot(self.zip_path)
        except ValidatorError as exc:
            self.findings.append(
                ValidationFinding(
                    code="ZIP_UNREADABLE",
                    severity="BLOCKER",
                    path=str(self.zip_path),
                    message=str(exc),
                    repair_instruction="Run stage_packager.py with the same contract and create the review zip before validation.",
                )
            )
            return self._finalize(expected_files, zip_entries=[])

        self._validate_zip_entries(zip_snapshot)
        self._validate_expected_files(expected_files, zip_snapshot)
        self._validate_required_categories(zip_snapshot)
        self._validate_zip_listing_log(zip_snapshot)
        self._validate_ledger(zip_snapshot)
        self._validate_evidence_files(expected_files, zip_snapshot)
        self._validate_screenshots(expected_files, zip_snapshot)
        self._validate_validator_outputs(zip_snapshot)
        self._validate_no_secret_like_entries(zip_snapshot)

        return self._finalize(expected_files, zip_entries=sorted(zip_snapshot.entries))

    def _validate_repo_root(self) -> List[ValidationFinding]:
        findings: List[ValidationFinding] = []
        for marker in as_list(dict_get(self.contract, "repository", "repo_markers", default=list(DEFAULT_REPO_MARKERS))):
            if not isinstance(marker, str):
                continue
            try:
                marker_path = safe_rel_to_path(self.repo_root, marker)
            except ValidatorError as exc:
                findings.append(
                    ValidationFinding(
                        code="INVALID_REPO_MARKER",
                        severity="HIGH",
                        path=marker,
                        message=str(exc),
                        repair_instruction="Fix repository.repo_markers in the contract to use repo-relative marker paths.",
                    )
                )
                continue
            if not marker_path.exists():
                findings.append(
                    ValidationFinding(
                        code="REPO_MARKER_MISSING",
                        severity="HIGH",
                        path=marker,
                        message=f"Repo marker missing from repo root: {marker}",
                        repair_instruction="Run validator from the correct repo root or fix repository.repo_markers.",
                    )
                )
        return findings

    def _validate_zip_entries(self, zip_snapshot: ZipSnapshot) -> None:
        if not zip_snapshot.entries:
            self.findings.append(
                ValidationFinding(
                    code="ZIP_EMPTY",
                    severity="BLOCKER",
                    path=str(self.zip_path),
                    message="Review zip contains no files.",
                    repair_instruction="Run stage_packager.py from repo root and ensure required files are copied before zipping.",
                )
            )

        for entry in sorted(zip_snapshot.entries):
            if not is_relative_repo_path(entry):
                self.findings.append(
                    ValidationFinding(
                        code="ZIP_PATH_NOT_REPO_RELATIVE",
                        severity="BLOCKER",
                        path=entry,
                        message="Zip entry is not a valid repo-relative path.",
                        repair_instruction="Recreate the zip from repo root using exact repo-relative paths only.",
                    )
                )
            for pattern in self.forbidden_patterns:
                if pattern.search(entry):
                    self.findings.append(
                        ValidationFinding(
                            code="FORBIDDEN_ZIP_ENTRY",
                            severity="BLOCKER",
                            path=entry,
                            message=f"Zip entry matches forbidden pattern: {pattern.pattern}",
                            repair_instruction="Remove forbidden entry and rerun stage_packager.py. Do not use changed/reference buckets or platform metadata.",
                        )
                    )

    def _validate_expected_files(self, expected_files: Mapping[str, ExpectedFile], zip_snapshot: ZipSnapshot) -> None:
        zip_path_rel = dict_get(self.contract, "review_export", "zip_path")
        output_dir_rel = dict_get(self.contract, "review_export", "output_dir")

        for path, expected in expected_files.items():
            if path in {zip_path_rel, output_dir_rel}:
                continue

            if self._is_secret_like(path):
                self.findings.append(
                    ValidationFinding(
                        code="SECRET_LIKE_EXPECTED_FILE",
                        severity="BLOCKER",
                        path=path,
                        message="Contract expects a secret-like file in the review export.",
                        repair_instruction="Remove this path from the contract or replace it with sanitized evidence.",
                        details={"sources": sorted(expected.sources)},
                    )
                )
                continue

            if self._is_excluded(path):
                # Excluded required files are a contract problem.
                if expected.required:
                    self.findings.append(
                        ValidationFinding(
                            code="REQUIRED_FILE_EXCLUDED_BY_POLICY",
                            severity="HIGH",
                            path=path,
                            message="Required file is excluded by review export policy.",
                            repair_instruction="Update contract to avoid requiring excluded files, or adjust policy deliberately.",
                            details={"sources": sorted(expected.sources)},
                        )
                    )
                continue

            repo_path = safe_rel_to_path(self.repo_root, path)
            exists_in_repo = repo_path.exists()
            exists_in_zip = zip_snapshot.has(path)

            if expected.required and not exists_in_repo:
                self.findings.append(
                    ValidationFinding(
                        code="REQUIRED_FILE_MISSING_IN_REPO",
                        severity="BLOCKER",
                        path=path,
                        message="Required file does not exist in repo.",
                        repair_instruction="Create/restore the required file, or update the contract only if the file is truly not required.",
                        details={"sources": sorted(expected.sources), "artifact_types": sorted(expected.artifact_types)},
                    )
                )
            elif not expected.required and not exists_in_repo:
                self.warnings.append(
                    ValidationFinding(
                        code="OPTIONAL_FILE_MISSING_IN_REPO",
                        severity="LOW",
                        path=path,
                        message="Optional expected file does not exist in repo.",
                        repair_instruction="No action required unless this file is needed for PASS.",
                        details={"sources": sorted(expected.sources), "artifact_types": sorted(expected.artifact_types)},
                    )
                )

            if exists_in_repo and expected.required and not exists_in_zip:
                self.findings.append(
                    ValidationFinding(
                        code="REQUIRED_FILE_MISSING_IN_ZIP",
                        severity="BLOCKER",
                        path=path,
                        message="Required repo file exists but is missing from review zip.",
                        repair_instruction="Rerun stage_packager.py so this file is copied into the export with its exact repo-relative path.",
                        details={"sources": sorted(expected.sources), "artifact_types": sorted(expected.artifact_types)},
                    )
                )
            elif exists_in_repo and not expected.required and not exists_in_zip:
                self.warnings.append(
                    ValidationFinding(
                        code="OPTIONAL_FILE_MISSING_IN_ZIP",
                        severity="LOW",
                        path=path,
                        message="Optional expected repo file exists but is missing from review zip.",
                        repair_instruction="Include it if it supports a PASS claim; otherwise document exclusion reason.",
                        details={"sources": sorted(expected.sources), "artifact_types": sorted(expected.artifact_types)},
                    )
                )

    def _validate_required_categories(self, zip_snapshot: ZipSnapshot) -> None:
        required_categories = set(
            str(item)
            for item in as_list(dict_get(self.contract, "review_export", "required_file_categories"))
            if isinstance(item, str)
        )
        if not required_categories:
            return
        present_categories = {detect_category(entry) for entry in zip_snapshot.entries}
        for category in sorted(required_categories - present_categories):
            self.findings.append(
                ValidationFinding(
                    code="REQUIRED_CATEGORY_MISSING",
                    severity="BLOCKER",
                    path=None,
                    message=f"Review zip is missing required file category: {category}",
                    repair_instruction=f"Include at least one relevant {category} file in the review export, with repo-relative path.",
                    details={"present_categories": sorted(present_categories)},
                )
            )

    def _validate_zip_listing_log(self, zip_snapshot: ZipSnapshot) -> None:
        configured = dict_get(self.contract, "review_export", "zip_listing_log_path")
        candidates: List[str] = []
        if isinstance(configured, str):
            candidates.append(normalize_rel_path(configured))
        candidates.extend(entry for entry in zip_snapshot.entries if entry.lower().endswith("zip-listing.log"))

        unique_candidates = sorted(set(candidates))
        if not unique_candidates:
            self.findings.append(
                ValidationFinding(
                    code="ZIP_LISTING_LOG_NOT_CONFIGURED",
                    severity="HIGH",
                    path=None,
                    message="No zip listing log path is configured or found.",
                    repair_instruction="Set review_export.zip_listing_log_path in the contract and rerun stage_packager.py.",
                )
            )
            return

        found = [path for path in unique_candidates if zip_snapshot.has(path)]
        if not found:
            self.findings.append(
                ValidationFinding(
                    code="ZIP_LISTING_LOG_MISSING",
                    severity="BLOCKER",
                    path=unique_candidates[0],
                    message="Zip listing log is missing from the review zip.",
                    repair_instruction="Run stage_packager.py so it writes and packages the raw zip listing log.",
                )
            )
            return

        for path in found:
            if zip_snapshot.size(path) <= 0:
                self.findings.append(
                    ValidationFinding(
                        code="ZIP_LISTING_LOG_EMPTY",
                        severity="HIGH",
                        path=path,
                        message="Zip listing log is empty.",
                        repair_instruction="Regenerate zip listing log from the final zip and include it.",
                    )
                )

    def _validate_ledger(self, zip_snapshot: ZipSnapshot) -> None:
        parser = LedgerParser(zip_snapshot)
        ledger_paths = parser.find_ledger_paths()
        if not ledger_paths:
            self.findings.append(
                ValidationFinding(
                    code="FILE_READ_LEDGER_MISSING",
                    severity="BLOCKER",
                    path=None,
                    message="No file-read ledger found in review zip.",
                    repair_instruction="Create and package the stage file-read ledger. It must list exact paths and zip inclusion claims.",
                )
            )
            return

        claims = parser.parse_all()
        for path, claim in sorted(claims.items()):
            if path.startswith("__PARSER_ERROR__:"):
                self.findings.append(
                    ValidationFinding(
                        code="FILE_READ_LEDGER_PARSE_ERROR",
                        severity="HIGH",
                        path=claim.get("ledger_path"),
                        message=f"Could not parse file-read ledger: {claim.get('parser_error')}",
                        repair_instruction="Fix the ledger format or use a JSON ledger with explicit path/included_in_zip/read_end_to_end fields.",
                    )
                )
                continue

            if claim.get("included_in_zip") is True and not zip_snapshot.has(path):
                self.findings.append(
                    ValidationFinding(
                        code="LEDGER_CLAIMS_INCLUDED_BUT_MISSING",
                        severity="BLOCKER",
                        path=path,
                        message="File-read ledger claims this file is included in zip, but the zip does not contain it.",
                        repair_instruction="Rerun stage_packager.py to include the file, or correct the ledger to stop claiming inclusion.",
                        details={"ledger_path": claim.get("ledger_path")},
                    )
                )

            if claim.get("read_end_to_end") is True and not zip_snapshot.has(path):
                self.findings.append(
                    ValidationFinding(
                        code="LEDGER_CLAIMS_READ_FILE_NOT_IN_ZIP",
                        severity="HIGH",
                        path=path,
                        message="Ledger claims end-to-end read, but the file is not packaged for reviewer verification.",
                        repair_instruction="Package the file with repo-relative path or mark the read claim as unsupported.",
                        details={"ledger_path": claim.get("ledger_path")},
                    )
                )

    def _validate_evidence_files(self, expected_files: Mapping[str, ExpectedFile], zip_snapshot: ZipSnapshot) -> None:
        evidence_paths = set()
        for path, expected in expected_files.items():
            if "log" in expected.artifact_types or "/logs/" in path or path.endswith(".log"):
                evidence_paths.add(path)

        for path in sorted(evidence_paths):
            if not zip_snapshot.has(path):
                continue
            if path not in zip_snapshot.entries:
                continue
            if zip_snapshot.size(path) <= 0:
                self.findings.append(
                    ValidationFinding(
                        code="EVIDENCE_LOG_EMPTY",
                        severity="HIGH",
                        path=path,
                        message="Evidence log is empty.",
                        repair_instruction="Rerun the validation command and save raw output to this log.",
                    )
                )
            else:
                try:
                    text = zip_snapshot.read_text(path, max_bytes=2_000_000)
                except Exception:
                    continue
                lower = text.lower()
                if "no tests collected" in lower and ("test" in path.lower() or "pytest" in lower):
                    self.findings.append(
                        ValidationFinding(
                            code="TEST_LOG_NO_TESTS_COLLECTED",
                            severity="HIGH",
                            path=path,
                            message="Test evidence log says no tests were collected.",
                            repair_instruction="Fix the test command/file so tests are collected, or mark test evidence PARTIAL honestly.",
                        )
                    )

    def _validate_screenshots(self, expected_files: Mapping[str, ExpectedFile], zip_snapshot: ZipSnapshot) -> None:
        screenshot_paths = set()
        for path, expected in expected_files.items():
            suffix = Path(path.lower()).suffix
            if "screenshot" in expected.artifact_types or suffix in SCREENSHOT_EXTENSIONS or "/screenshots/" in path:
                screenshot_paths.add(path)

        for path in sorted(screenshot_paths):
            if not zip_snapshot.has(path):
                continue
            if path not in zip_snapshot.entries:
                continue
            size = zip_snapshot.size(path)
            if size <= 0:
                self.findings.append(
                    ValidationFinding(
                        code="SCREENSHOT_EMPTY",
                        severity="HIGH",
                        path=path,
                        message="Screenshot file is empty.",
                        repair_instruction="Re-capture the screenshot and package it.",
                    )
                )
                continue
            if size < 5_000:
                self.warnings.append(
                    ValidationFinding(
                        code="SCREENSHOT_SMALL",
                        severity="LOW",
                        path=path,
                        message=f"Screenshot is small ({size} bytes); may be blank or placeholder.",
                        repair_instruction="Manually inspect screenshot; recapture if it does not show loaded UI.",
                    )
                )
            if Path(path.lower()).suffix == ".png":
                try:
                    raw = zip_snapshot.read_bytes(path, max_bytes=32)
                    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                        self.findings.append(
                            ValidationFinding(
                                code="SCREENSHOT_PNG_HEADER_INVALID",
                                severity="HIGH",
                                path=path,
                                message="PNG screenshot does not have a valid PNG header.",
                                repair_instruction="Re-capture the screenshot as a valid PNG.",
                            )
                        )
                except Exception as exc:
                    self.findings.append(
                        ValidationFinding(
                            code="SCREENSHOT_UNREADABLE",
                            severity="HIGH",
                            path=path,
                            message=f"Screenshot could not be read: {exc}",
                            repair_instruction="Re-capture and package the screenshot.",
                        )
                    )

    def _validate_validator_outputs(self, zip_snapshot: ZipSnapshot) -> None:
        if not dict_get(self.contract, "review_export", "include_validator_outputs", default=True):
            return
        outputs = [
            entry for entry in zip_snapshot.entries
            if entry.startswith("tests/results/evidence/validator_outputs/")
            and entry.endswith(".json")
        ]
        if not outputs:
            self.findings.append(
                ValidationFinding(
                    code="VALIDATOR_OUTPUTS_MISSING",
                    severity="HIGH",
                    path="tests/results/evidence/validator_outputs/",
                    message="Review zip does not include validator output JSON files.",
                    repair_instruction="Run validators, then rerun stage_packager.py so validator outputs are included in the final zip.",
                )
            )

    def _validate_no_secret_like_entries(self, zip_snapshot: ZipSnapshot) -> None:
        for entry in sorted(zip_snapshot.entries):
            if self._is_secret_like(entry):
                self.findings.append(
                    ValidationFinding(
                        code="SECRET_LIKE_ZIP_ENTRY",
                        severity="BLOCKER",
                        path=entry,
                        message="Review zip contains a secret-like file path.",
                        repair_instruction="Remove secrets from review export and use sanitized evidence if needed.",
                    )
                )

    def _is_excluded(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        name = normalized.split("/")[-1]
        for pattern in self.exclude_globs:
            if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern):
                return True
        return False

    def _is_secret_like(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        name = normalized.split("/")[-1]
        for pattern in DEFAULT_SECRET_GLOBS:
            if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern):
                return True
        return False

    def _finalize(self, expected_files: Mapping[str, ExpectedFile], zip_entries: Sequence[str]) -> Tuple[str, Dict[str, Any]]:
        status = self._derive_status()
        report = self._build_report(status, expected_files, zip_entries)
        write_json(self.report_out, report)
        return status, report

    def _derive_status(self) -> str:
        if any(f.severity in {"BLOCKER", "HIGH"} for f in self.findings):
            return STATUS_NO_GO
        if self.findings or self.warnings:
            return STATUS_PARTIAL
        return STATUS_PASS

    def _build_report(self, status: str, expected_files: Mapping[str, ExpectedFile], zip_entries: Sequence[str]) -> Dict[str, Any]:
        category_counts = defaultdict(int)
        for entry in zip_entries:
            category_counts[detect_category(entry)] += 1

        findings = [dataclasses.asdict(f) for f in self.findings]
        warnings = [dataclasses.asdict(f) for f in self.warnings]

        next_action = self._next_action(status)

        return {
            "generated_by": "review_export_validator.py",
            "generated_at": utc_now_iso(),
            "status": status,
            "contract_id": self.contract.get("contract_id"),
            "stage_id": dict_get(self.contract, "stage", "stage_id"),
            "stage_title": dict_get(self.contract, "stage", "stage_title"),
            "repo_root": str(self.repo_root),
            "contract_path": self.contract_rel_path or str(self.contract_path),
            "zip_path": str(self.zip_path),
            "report_path": self._report_rel_or_abs(),
            "counts": {
                "expected_files": len(expected_files),
                "zip_entries": len(zip_entries),
                "findings": len(findings),
                "warnings": len(warnings),
                "blocker_or_high_findings": len([f for f in self.findings if f.severity in {"BLOCKER", "HIGH"}]),
                "zip_category_counts": dict(sorted(category_counts.items())),
            },
            "findings": findings,
            "warnings": warnings,
            "expected_files": [
                {
                    "path": item.path,
                    "required": item.required,
                    "sources": sorted(item.sources),
                    "artifact_types": sorted(item.artifact_types),
                }
                for item in expected_files.values()
            ],
            "zip_entries": list(zip_entries),
            "next_action": next_action,
        }

    def _report_rel_or_abs(self) -> str:
        try:
            return self.report_out.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return str(self.report_out)

    def _next_action(self, status: str) -> Dict[str, Any]:
        if status == STATUS_PASS:
            return {
                "action_type": "manual_review",
                "title": "Review export mechanically valid; proceed to manual source-grounded review.",
                "instructions": [
                    "Read all changed source/config/test files end-to-end.",
                    "Read relevant unchanged source files required by the contract.",
                    "Inspect screenshots manually for loaded UI and claimed behavior.",
                    "Review logs for actual command output and status codes.",
                    "Do not accept stage completion from validator status alone.",
                ],
            }

        grouped: Dict[str, List[ValidationFinding]] = defaultdict(list)
        for finding in self.findings:
            grouped[finding.code].append(finding)

        instructions: List[str] = []
        allowed_paths: Set[str] = set()

        def add_group(code: str, message: str) -> None:
            if code in grouped:
                count = len(grouped[code])
                examples = [f.path for f in grouped[code] if f.path][:8]
                detail = f"{message} Count={count}."
                if examples:
                    detail += f" Examples={examples}."
                    allowed_paths.update(path for path in examples if path)
                instructions.append(detail)

        add_group("ZIP_UNREADABLE", "Run stage_packager.py to create the configured review zip.")
        add_group("ZIP_EMPTY", "Recreate the review zip; it contains no files.")
        add_group("ZIP_PATH_NOT_REPO_RELATIVE", "Recreate zip from repo root with exact repo-relative paths only.")
        add_group("FORBIDDEN_ZIP_ENTRY", "Remove forbidden zip entries such as changed/, reference/, __MACOSX, .DS_Store, build outputs.")
        add_group("REQUIRED_FILE_MISSING_IN_REPO", "Create/restore required repo files, or update contract only if truly not required.")
        add_group("REQUIRED_FILE_MISSING_IN_ZIP", "Rerun stage_packager.py so existing required files are copied into the zip.")
        add_group("REQUIRED_CATEGORY_MISSING", "Include required backend/frontend/tests/evidence/config/scripts/docs categories.")
        add_group("ZIP_LISTING_LOG_MISSING", "Generate and package sprXX-zip-listing.log.")
        add_group("FILE_READ_LEDGER_MISSING", "Create and package the file-read ledger.")
        add_group("LEDGER_CLAIMS_INCLUDED_BUT_MISSING", "Fix ledger/package mismatch: include claimed files or correct ledger.")
        add_group("LEDGER_CLAIMS_READ_FILE_NOT_IN_ZIP", "Package files claimed as read end-to-end for reviewer verification.")
        add_group("EVIDENCE_LOG_EMPTY", "Rerun validation commands and save raw non-empty logs.")
        add_group("TEST_LOG_NO_TESTS_COLLECTED", "Fix test command/file or mark tests PARTIAL honestly.")
        add_group("SCREENSHOT_EMPTY", "Re-capture empty screenshots.")
        add_group("SCREENSHOT_PNG_HEADER_INVALID", "Re-capture invalid PNG screenshots.")
        add_group("VALIDATOR_OUTPUTS_MISSING", "Run validators, then rerun stage_packager.py to include validator outputs.")
        add_group("SECRET_LIKE_ZIP_ENTRY", "Remove secret-like files from zip.")

        if not instructions:
            instructions.append("Inspect validator findings and apply the smallest packaging/evidence correction. Do not broaden implementation scope.")

        return {
            "action_type": "fix_packaging",
            "title": "Fix review export packaging/evidence before manual review.",
            "allowed_files": {
                "read": sorted(allowed_paths),
                "edit": sorted(allowed_paths),
                "include_in_zip": sorted(allowed_paths),
                "evidence": [],
                "screenshots": [],
            },
            "instructions": instructions,
        }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate BhojanGo stage review export zip against a stage contract.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--contract", required=True, help="Repo-relative or absolute path to stage contract JSON.")
    parser.add_argument("--repo-root", default=None, help="Repo root. Defaults to nearest parent with package.json and pnpm-workspace.yaml.")
    parser.add_argument("--zip", dest="zip_override", default=None, help="Optional override path to review zip.")
    parser.add_argument("--report-out", default=None, help="Optional output path for validation report JSON.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress.")
    return parser.parse_args(argv)


def resolve_config(args: argparse.Namespace) -> ValidatorConfig:
    start = Path.cwd()
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else infer_repo_root(start)

    contract_arg = Path(args.contract).expanduser()
    contract_path = contract_arg.resolve() if contract_arg.is_absolute() else (repo_root / contract_arg).resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        raise ValidatorError(f"Repo root is not a directory: {repo_root}")
    if not contract_path.exists() or not contract_path.is_file():
        raise ValidatorError(f"Contract file is not found: {contract_path}")

    zip_override = None
    if args.zip_override:
        zip_arg = Path(args.zip_override).expanduser()
        zip_override = zip_arg.resolve() if zip_arg.is_absolute() else (repo_root / zip_arg).resolve()

    report_out = None
    if args.report_out:
        report_arg = Path(args.report_out).expanduser()
        report_out = report_arg.resolve() if report_arg.is_absolute() else (repo_root / report_arg).resolve()

    return ValidatorConfig(
        repo_root=repo_root,
        contract_path=contract_path,
        zip_override=zip_override,
        report_out=report_out,
        verbose=bool(args.verbose),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        config = resolve_config(args)
        validator = ReviewExportValidator(config)
        status, report = validator.validate()

        summary = {
            "status": status,
            "contract_id": report.get("contract_id"),
            "stage_id": report.get("stage_id"),
            "zip_path": report.get("zip_path"),
            "report_path": report.get("report_path"),
            "zip_entries": report.get("counts", {}).get("zip_entries"),
            "findings": report.get("counts", {}).get("findings"),
            "warnings": report.get("counts", {}).get("warnings"),
            "next_action": report.get("next_action", {}).get("title"),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        return 0 if status == STATUS_PASS else 1

    except ValidatorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: interrupted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
