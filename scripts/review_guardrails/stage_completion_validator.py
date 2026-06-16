#!/usr/bin/env python3
"""
stage_completion_validator.py

Task-level mechanical validator for BhojanGo stage contracts.

Purpose
-------
This script validates micro-task completion against a stage contract JSON.

It checks task-level proof such as:
- file existence / non-empty files
- Python functions/classes/routes/imports
- TypeScript/React components/imports
- code regex presence/absence
- migration column additions
- package.json script existence
- logs containing or not containing expected patterns
- curl/status-code evidence
- command exit-code evidence
- screenshot existence/basic validity
- pytest collection evidence
- JSON path equality
- forbidden code strings
- allowed-files-only change discipline
- source/evidence files included in final zip

It emits results by task_id so Kimchi can fix only the failing task(s).
It also emits a compact kimchi_next_prompt and cost_control_for_followup
block to avoid broad follow-up prompts and silent token burn.

This is not a manual reviewer. It validates mechanical proof only.

Typical usage
-------------
From repo root:

    python scripts/review_guardrails/stage_completion_validator.py \
      --contract review_contracts/SPR-02-v3.contract.json

Optional:

    python scripts/review_guardrails/stage_completion_validator.py \
      --contract review_contracts/SPR-02-v3.contract.json \
      --task SPR-02.T002

Exit codes
----------
0 = all mechanically required validators passed
1 = at least one task PARTIAL/NO-GO
2 = invalid arguments / unreadable contract / fatal validator setup error
"""

from __future__ import annotations

import argparse
import ast
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
STATUS_NOT_RUN = "NOT-RUN"

DEFAULT_REPO_MARKERS = ("package.json", "pnpm-workspace.yaml")

SEVERITY_ORDER = {
    "BLOCKER": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "INFO": 1,
}

SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

FORBIDDEN_DEFAULT_PATTERNS_BEFORE_PR08 = [
    r"unsplash\.com",
    r"api\.unsplash\.com",
    r"maps\.googleapis\.com",
    r"twilio",
    r"sendgrid",
    r"stripe",
    r"razorpay",
    r"aws_access_key",
    r"aws_secret_access_key",
    r"s3://",
    r"opensearch.*required",
]


class CompletionValidatorError(Exception):
    """Fatal stage completion validator error."""


@dataclasses.dataclass
class ValidatorOutcome:
    task_id: str
    scope_id: str
    validator_id: str
    validator_type: str
    status: str
    severity: str
    path: Optional[str]
    message: str
    repair_instruction: str
    evidence_acceptance: Optional[str] = None
    manual_review_required: bool = False
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class TaskResult:
    task_id: str
    scope_id: str
    title: str
    sequence: int
    status: str
    failed_count: int
    passed_count: int
    manual_review_required_count: int
    outcomes: List[ValidatorOutcome]


@dataclasses.dataclass
class ValidatorConfig:
    repo_root: Path
    contract_path: Path
    task_filter: Optional[str] = None
    zip_override: Optional[Path] = None
    report_out: Optional[Path] = None
    verbose: bool = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompletionValidatorError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CompletionValidatorError(f"Invalid JSON in {path}: {exc}") from exc


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
        raise CompletionValidatorError(f"Invalid repo-relative path: {raw!r}")
    return value


def safe_rel_to_path(repo_root: Path, rel_path: str) -> Path:
    rel = normalize_rel_path(rel_path)
    candidate = (repo_root / rel).resolve()
    root = repo_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CompletionValidatorError(f"Path escapes repo root: {rel_path}") from exc
    return candidate


def infer_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if all((candidate / marker).exists() for marker in DEFAULT_REPO_MARKERS):
            return candidate
    return current


def read_text_file(path: Path, max_bytes: int = 5_000_000) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.is_dir():
        raise IsADirectoryError(str(path))
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"File too large to read as text: {path} ({size} bytes)")
    return path.read_text(encoding="utf-8", errors="replace")


def regex_search(pattern: str, text: str, flags: int = re.IGNORECASE | re.MULTILINE | re.DOTALL) -> bool:
    return re.search(pattern, text, flags) is not None


class ZipSnapshot:
    """Optional read-only snapshot of configured review zip."""

    def __init__(self, zip_path: Optional[Path]) -> None:
        self.zip_path = zip_path
        self.entries: Dict[str, zipfile.ZipInfo] = {}
        if zip_path is not None:
            self._load()

    def _load(self) -> None:
        if self.zip_path is None or not self.zip_path.exists():
            return
        try:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                for info in zf.infolist():
                    name = info.filename.replace("\\", "/")
                    if not name.endswith("/"):
                        self.entries[name] = info
        except zipfile.BadZipFile:
            # Stage completion validators that need zip will fail with zip missing/unreadable.
            self.entries = {}

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


class StageCompletionValidator:
    """Validate every task's validators against repo files and evidence."""

    def __init__(self, config: ValidatorConfig) -> None:
        self.config = config
        self.repo_root = config.repo_root.resolve()
        self.contract_path = config.contract_path
        self.contract = load_json(config.contract_path)
        self.contract_rel_path = self._contract_rel_path()

        zip_path = config.zip_override
        if zip_path is None:
            zip_path_raw = dict_get(self.contract, "review_export", "zip_path")
            if isinstance(zip_path_raw, str):
                zip_path = safe_rel_to_path(self.repo_root, zip_path_raw)
        self.zip = ZipSnapshot(zip_path)

        self.report_out = config.report_out or self._default_report_out()

    def _contract_rel_path(self) -> Optional[str]:
        try:
            return self.contract_path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return None

    def _default_report_out(self) -> Path:
        contract_id = str(self.contract.get("contract_id") or "stage").replace("/", "_")
        return safe_rel_to_path(
            self.repo_root,
            f"tests/results/evidence/validator_outputs/{contract_id}_stage_completion_validation.json",
        )

    def validate(self) -> Tuple[str, Dict[str, Any]]:
        tasks = self._selected_tasks()
        task_results: List[TaskResult] = []

        for task in tasks:
            result = self._validate_task(task)
            task_results.append(result)

        overall_status = self._derive_overall_status(task_results)
        report = self._build_report(overall_status, task_results)
        write_json(self.report_out, report)
        return overall_status, report

    def _selected_tasks(self) -> List[Mapping[str, Any]]:
        tasks = [t for t in as_list(self.contract.get("task_sequence")) if isinstance(t, Mapping)]
        tasks.sort(key=lambda t: int(t.get("sequence", 999999)))
        if self.config.task_filter:
            tasks = [t for t in tasks if t.get("task_id") == self.config.task_filter]
            if not tasks:
                raise CompletionValidatorError(f"Task not found in contract: {self.config.task_filter}")
        return tasks

    def _validate_task(self, task: Mapping[str, Any]) -> TaskResult:
        task_id = str(task.get("task_id") or "UNKNOWN_TASK")
        scope_id = str(task.get("scope_id") or "UNKNOWN_SCOPE")
        title = str(task.get("title") or "")
        sequence = int(task.get("sequence") or 999999)

        outcomes: List[ValidatorOutcome] = []
        for validator in as_list(task.get("validators")):
            if not isinstance(validator, Mapping):
                continue
            outcomes.append(self._run_validator(task, validator))

        passed_count = len([o for o in outcomes if o.status == STATUS_PASS])
        failed = [o for o in outcomes if o.status != STATUS_PASS and not o.manual_review_required]
        manual_count = len([o for o in outcomes if o.manual_review_required])

        task_status = self._derive_task_status(task, outcomes)

        return TaskResult(
            task_id=task_id,
            scope_id=scope_id,
            title=title,
            sequence=sequence,
            status=task_status,
            failed_count=len(failed),
            passed_count=passed_count,
            manual_review_required_count=manual_count,
            outcomes=outcomes,
        )

    def _derive_task_status(self, task: Mapping[str, Any], outcomes: Sequence[ValidatorOutcome]) -> str:
        if not outcomes:
            return STATUS_NOT_RUN

        hard_failures = [
            o for o in outcomes
            if o.status != STATUS_PASS and SEVERITY_ORDER.get(o.severity, 0) >= SEVERITY_ORDER["HIGH"]
        ]
        soft_failures = [
            o for o in outcomes
            if o.status != STATUS_PASS and SEVERITY_ORDER.get(o.severity, 0) < SEVERITY_ORDER["HIGH"]
        ]

        if hard_failures:
            return STATUS_NO_GO
        if soft_failures:
            return STATUS_PARTIAL

        # Mechanical PASS can still require manual review, but that does not make
        # the mechanical validator fail. The report flags manual review separately.
        return STATUS_PASS

    def _derive_overall_status(self, task_results: Sequence[TaskResult]) -> str:
        if any(t.status == STATUS_NO_GO for t in task_results):
            return STATUS_NO_GO
        if any(t.status in {STATUS_PARTIAL, STATUS_NOT_RUN} for t in task_results):
            return STATUS_PARTIAL
        return STATUS_PASS

    def _run_validator(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        validator_type = str(validator.get("type") or "")
        runner = getattr(self, f"_validate_{validator_type}", None)

        if runner is None:
            return self._outcome(
                task,
                validator,
                STATUS_NO_GO,
                f"Unsupported validator type: {validator_type}",
                "Update stage_completion_validator.py to support this validator type, or change the contract to use a supported validator.",
            )

        try:
            return runner(task, validator)
        except Exception as exc:
            return self._outcome(
                task,
                validator,
                STATUS_NO_GO,
                f"Validator raised error: {exc}",
                self._repair_instruction(task, validator),
                details={"exception_type": type(exc).__name__},
            )

    def _outcome(
        self,
        task: Mapping[str, Any],
        validator: Mapping[str, Any],
        status: str,
        message: str,
        repair_instruction: str,
        *,
        path: Optional[str] = None,
        evidence_acceptance: Optional[str] = None,
        manual_review_required: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ValidatorOutcome:
        return ValidatorOutcome(
            task_id=str(task.get("task_id") or "UNKNOWN_TASK"),
            scope_id=str(task.get("scope_id") or "UNKNOWN_SCOPE"),
            validator_id=str(validator.get("validator_id") or "UNKNOWN_VALIDATOR"),
            validator_type=str(validator.get("type") or "UNKNOWN_TYPE"),
            status=status,
            severity=str(validator.get("severity") or "HIGH"),
            path=path or validator.get("path") or validator.get("zip_path"),
            message=message,
            repair_instruction=repair_instruction,
            evidence_acceptance=evidence_acceptance,
            manual_review_required=bool(
                validator.get("manual_review_required")
                if manual_review_required is None
                else manual_review_required
            ),
            details=details or {},
        )

    def _pass(
        self,
        task: Mapping[str, Any],
        validator: Mapping[str, Any],
        message: str,
        *,
        path: Optional[str] = None,
        evidence_acceptance: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ValidatorOutcome:
        return self._outcome(
            task,
            validator,
            STATUS_PASS,
            message,
            self._repair_instruction(task, validator),
            path=path,
            evidence_acceptance=evidence_acceptance,
            details=details,
        )

    def _fail(
        self,
        task: Mapping[str, Any],
        validator: Mapping[str, Any],
        message: str,
        *,
        path: Optional[str] = None,
        repair_instruction: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ValidatorOutcome:
        return self._outcome(
            task,
            validator,
            STATUS_NO_GO,
            message,
            repair_instruction or self._repair_instruction(task, validator),
            path=path,
            details=details,
        )

    def _repair_instruction(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> str:
        return str(validator.get("repair_instruction") or task.get("repair_instruction") or "Fix this validator failure only. Do not broaden scope.")

    def _path_from_validator(self, validator: Mapping[str, Any]) -> str:
        path = validator.get("path")
        if not isinstance(path, str):
            raise CompletionValidatorError("validator.path is required")
        return normalize_rel_path(path)

    def _repo_path(self, validator: Mapping[str, Any]) -> Tuple[str, Path]:
        rel = self._path_from_validator(validator)
        return rel, safe_rel_to_path(self.repo_root, rel)

    def _read_validator_text(self, validator: Mapping[str, Any]) -> Tuple[str, str]:
        rel, path = self._repo_path(validator)
        return rel, read_text_file(path)

    # ---------------------------------------------------------------------
    # File validators
    # ---------------------------------------------------------------------

    def _validate_file_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, path = self._repo_path(validator)
        if path.exists():
            return self._pass(task, validator, "File exists.", path=rel, evidence_acceptance="repo file exists")
        return self._fail(task, validator, "File missing in repo.", path=rel)

    def _validate_file_not_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, path = self._repo_path(validator)
        if not path.exists():
            return self._pass(task, validator, "File does not exist as expected.", path=rel, evidence_acceptance="repo file absent")
        return self._fail(task, validator, "File exists but validator expected it to be absent.", path=rel)

    def _validate_file_nonempty(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, path = self._repo_path(validator)
        if not path.exists():
            return self._fail(task, validator, "File missing in repo.", path=rel)
        if path.is_dir():
            return self._fail(task, validator, "Path is a directory, expected file.", path=rel)
        size = path.stat().st_size
        min_size = int(validator.get("min_size_bytes") or 1)
        if size >= min_size:
            return self._pass(task, validator, f"File is non-empty: {size} bytes.", path=rel, evidence_acceptance=f"size >= {min_size} bytes")
        return self._fail(task, validator, f"File too small: {size} bytes; expected >= {min_size}.", path=rel)

    def _validate_file_size_between(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, path = self._repo_path(validator)
        if not path.exists() or not path.is_file():
            return self._fail(task, validator, "File missing or not a file.", path=rel)
        size = path.stat().st_size
        min_size = int(validator.get("min_size_bytes") or 0)
        max_size = int(validator.get("max_size_bytes") or 10**18)
        if min_size <= size <= max_size:
            return self._pass(task, validator, f"File size {size} is within range.", path=rel, evidence_acceptance=f"{min_size} <= size <= {max_size}")
        return self._fail(task, validator, f"File size {size} outside range {min_size}..{max_size}.", path=rel)

    # ---------------------------------------------------------------------
    # Zip validators
    # ---------------------------------------------------------------------

    def _validate_zip_contains(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel = normalize_rel_path(str(validator.get("path") or validator.get("zip_path") or ""))
        if not self.zip.entries:
            return self._fail(task, validator, "Review zip not loaded or empty.", path=rel)
        if self.zip.has(rel):
            return self._pass(task, validator, "Zip contains expected path.", path=rel, evidence_acceptance="zip entry exists")
        return self._fail(task, validator, "Zip missing expected path.", path=rel, repair_instruction="Rerun stage_packager.py so this path is included with repo-relative path.")

    def _validate_zip_not_contains(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel = normalize_rel_path(str(validator.get("path") or validator.get("zip_path") or ""))
        if not self.zip.has(rel):
            return self._pass(task, validator, "Zip does not contain forbidden path.", path=rel, evidence_acceptance="zip entry absent")
        return self._fail(task, validator, "Zip contains path that should not be included.", path=rel)

    def _validate_zip_no_forbidden_entries(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        patterns = [str(p) for p in validator.get("patterns") or []]
        if not patterns:
            patterns = [r"(^|/)__MACOSX(/|$)", r"(^|/)\.DS_Store$", r"(^|/)changed(/|$)", r"(^|/)reference(/|$)"]
        compiled = [re.compile(p) for p in patterns]
        matches = []
        for entry in self.zip.entries:
            for pattern in compiled:
                if pattern.search(entry):
                    matches.append({"entry": entry, "pattern": pattern.pattern})
        if not matches:
            return self._pass(task, validator, "Zip has no forbidden entries.", evidence_acceptance="no forbidden zip entries matched")
        return self._fail(
            task,
            validator,
            f"Zip contains forbidden entries: {len(matches)}",
            details={"matches": matches[:50]},
            repair_instruction="Recreate zip from repo root; remove changed/reference folders, __MACOSX, .DS_Store, and build artifacts.",
        )

    def _validate_zip_contains_required_files(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        paths = [normalize_rel_path(p) for p in as_list(validator.get("paths")) if isinstance(p, str)]
        missing = [path for path in paths if not self.zip.has(path)]
        if not missing:
            return self._pass(task, validator, "Zip contains all required files.", evidence_acceptance=f"{len(paths)} required paths present")
        return self._fail(
            task,
            validator,
            f"Zip missing required files: {len(missing)}",
            details={"missing": missing},
            repair_instruction="Rerun stage_packager.py; do not manually flatten or omit required files.",
        )

    def _validate_source_files_included(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        return self._validate_zip_contains_required_files(task, validator)

    def _validate_evidence_files_included(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        return self._validate_zip_contains_required_files(task, validator)

    def _validate_validator_output_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        return self._validate_zip_contains(task, validator)

    def _validate_ledger_matches_zip(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, ledger_path = self._repo_path(validator)
        if not ledger_path.exists():
            return self._fail(task, validator, "Ledger file missing in repo.", path=rel)
        text = read_text_file(ledger_path)
        claimed = self._extract_included_claims_from_ledger(text)
        missing = [path for path in claimed if not self.zip.has(path)]
        if not missing:
            return self._pass(task, validator, "Ledger included-in-zip claims match zip.", path=rel, evidence_acceptance=f"{len(claimed)} ledger claims checked")
        return self._fail(
            task,
            validator,
            f"Ledger claims files included but zip is missing {len(missing)} files.",
            path=rel,
            details={"missing": missing},
            repair_instruction="Rerun stage_packager.py or correct the ledger; do not claim inclusion unless the file is in the zip.",
        )

    @staticmethod
    def _extract_included_claims_from_ledger(text: str) -> List[str]:
        claims: Set[str] = set()
        for line in text.splitlines():
            if "|" not in line:
                continue
            lower = line.lower()
            if "yes" not in lower and "true" not in lower and "included" not in lower:
                continue
            for match in re.findall(r"(?:services|apps|tests|scripts|docs|review_contracts|packages|infra)/[A-Za-z0-9_./()\[\]\-]+", line):
                if is_relative_repo_path(match):
                    claims.add(normalize_rel_path(match.strip("`|,")))
        return sorted(claims)

    # ---------------------------------------------------------------------
    # Python validators
    # ---------------------------------------------------------------------

    def _validate_python_function_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        function_name = str(validator.get("function_name") or "")
        if not function_name:
            return self._fail(task, validator, "function_name is required.", path=rel)
        tree = ast.parse(text)
        found = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name for node in ast.walk(tree))
        if found:
            return self._pass(task, validator, f"Python function exists: {function_name}", path=rel, evidence_acceptance="AST function definition found")
        return self._fail(task, validator, f"Python function not found: {function_name}", path=rel)

    def _validate_python_class_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        class_name = str(validator.get("class_name") or "")
        if not class_name:
            return self._fail(task, validator, "class_name is required.", path=rel)
        tree = ast.parse(text)
        found = any(isinstance(node, ast.ClassDef) and node.name == class_name for node in ast.walk(tree))
        if found:
            return self._pass(task, validator, f"Python class exists: {class_name}", path=rel, evidence_acceptance="AST class definition found")
        return self._fail(task, validator, f"Python class not found: {class_name}", path=rel)

    def _validate_python_ast_import_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        import_name = str(validator.get("import_name") or "")
        from_module = validator.get("from_module")
        if not import_name:
            return self._fail(task, validator, "import_name is required.", path=rel)
        tree = ast.parse(text)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == import_name or alias.asname == import_name for alias in node.names):
                    found = True
                    break
            elif isinstance(node, ast.ImportFrom):
                module_match = from_module is None or node.module == from_module
                if module_match and any(alias.name == import_name or alias.asname == import_name for alias in node.names):
                    found = True
                    break
        if found:
            return self._pass(task, validator, f"Python import exists: {import_name}", path=rel, evidence_acceptance="AST import found")
        return self._fail(task, validator, f"Python import not found: {import_name}", path=rel)

    def _validate_python_route_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        route = str(validator.get("route") or "")
        method = str(validator.get("method") or "").lower()
        if not route:
            return self._fail(task, validator, "route is required.", path=rel)

        route_escaped = re.escape(route)
        method_pattern = method if method else r"(get|post|put|patch|delete|options|head)"
        decorator_pattern = rf"@\s*[\w.]*\.(?:{method_pattern})\s*\(\s*['\"]{route_escaped}['\"]"
        add_route_pattern = rf"add_api_route\s*\(\s*['\"]{route_escaped}['\"].*methods\s*=\s*\[[^\]]*['\"]{method.upper()}['\"]"

        if regex_search(decorator_pattern, text) or (method and regex_search(add_route_pattern, text)):
            return self._pass(task, validator, f"Python route exists: {method.upper() if method else '*'} {route}", path=rel, evidence_acceptance="route decorator/add_api_route found")

        return self._fail(task, validator, f"Python route not found: {method.upper() if method else '*'} {route}", path=rel)

    # ---------------------------------------------------------------------
    # TypeScript / code validators
    # ---------------------------------------------------------------------

    def _validate_typescript_component_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        component = str(validator.get("component_name") or "")
        if not component:
            return self._fail(task, validator, "component_name is required.", path=rel)
        patterns = [
            rf"export\s+default\s+function\s+{re.escape(component)}\s*\(",
            rf"export\s+function\s+{re.escape(component)}\s*\(",
            rf"function\s+{re.escape(component)}\s*\(",
            rf"const\s+{re.escape(component)}\s*[:=]",
            rf"export\s+const\s+{re.escape(component)}\s*[:=]",
            rf"class\s+{re.escape(component)}\s+extends\s+",
        ]
        if any(regex_search(pattern, text) for pattern in patterns):
            return self._pass(task, validator, f"TypeScript/React component exists: {component}", path=rel, evidence_acceptance="component declaration found")
        return self._fail(task, validator, f"Component not found: {component}", path=rel)

    def _validate_typescript_import_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        import_name = str(validator.get("import_name") or "")
        from_module = validator.get("from_module")
        if not import_name:
            return self._fail(task, validator, "import_name is required.", path=rel)

        if from_module:
            module = re.escape(str(from_module))
            patterns = [
                rf"import\s+\{{[^}}]*\b{re.escape(import_name)}\b[^}}]*\}}\s+from\s+['\"]{module}['\"]",
                rf"import\s+{re.escape(import_name)}\s+from\s+['\"]{module}['\"]",
                rf"import\s+\*\s+as\s+{re.escape(import_name)}\s+from\s+['\"]{module}['\"]",
            ]
        else:
            patterns = [
                rf"import\s+\{{[^}}]*\b{re.escape(import_name)}\b[^}}]*\}}\s+from\s+['\"]",
                rf"import\s+{re.escape(import_name)}\s+from\s+['\"]",
                rf"import\s+\*\s+as\s+{re.escape(import_name)}\s+from\s+['\"]",
            ]

        if any(regex_search(pattern, text) for pattern in patterns):
            return self._pass(task, validator, f"TypeScript import exists: {import_name}", path=rel, evidence_acceptance="import statement found")
        return self._fail(task, validator, f"TypeScript import not found: {import_name}", path=rel)

    def _validate_code_regex_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        pattern = str(validator.get("pattern") or "")
        if not pattern:
            return self._fail(task, validator, "pattern is required.", path=rel)
        if regex_search(pattern, text):
            return self._pass(task, validator, "Code regex found.", path=rel, evidence_acceptance=f"regex matched: {pattern}")
        return self._fail(task, validator, f"Code regex not found: {pattern}", path=rel)

    def _validate_code_regex_not_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        pattern = str(validator.get("pattern") or "")
        if not pattern:
            return self._fail(task, validator, "pattern is required.", path=rel)
        if not regex_search(pattern, text):
            return self._pass(task, validator, "Forbidden code regex absent.", path=rel, evidence_acceptance=f"regex absent: {pattern}")
        return self._fail(task, validator, f"Forbidden code regex found: {pattern}", path=rel)

    def _validate_migration_adds_column(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        table = str(validator.get("table") or "")
        column = str(validator.get("column") or "")
        if not table or not column:
            return self._fail(task, validator, "table and column are required.", path=rel)

        patterns = [
            rf"op\.add_column\s*\(\s*['\"]{re.escape(table)}['\"]\s*,\s*sa\.Column\s*\(\s*['\"]{re.escape(column)}['\"]",
            rf"ALTER\s+TABLE\s+{re.escape(table)}\s+ADD\s+COLUMN\s+{re.escape(column)}",
            rf"addColumn\s*\(\s*['\"]{re.escape(table)}['\"]\s*,\s*['\"]{re.escape(column)}['\"]",
        ]
        if any(regex_search(pattern, text) for pattern in patterns):
            return self._pass(task, validator, f"Migration adds column {table}.{column}.", path=rel, evidence_acceptance="migration add-column pattern found")
        return self._fail(task, validator, f"Migration does not add expected column {table}.{column}.", path=rel)

    def _validate_package_script_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, path = self._repo_path(validator)
        if not path.exists():
            return self._fail(task, validator, "package.json missing.", path=rel)
        data = json.loads(read_text_file(path))
        script_name = str(validator.get("function_name") or validator.get("metadata", {}).get("script_name") or "")
        if not script_name:
            return self._fail(task, validator, "script name required in function_name or metadata.script_name.", path=rel)
        scripts = data.get("scripts") or {}
        if script_name in scripts:
            return self._pass(task, validator, f"package.json script exists: {script_name}", path=rel, evidence_acceptance="scripts entry exists")
        return self._fail(task, validator, f"package.json script missing: {script_name}", path=rel)

    # ---------------------------------------------------------------------
    # Log / command validators
    # ---------------------------------------------------------------------

    def _validate_log_contains_regex(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        pattern = str(validator.get("pattern") or "")
        must_contain = [str(p) for p in as_list(validator.get("must_contain")) if isinstance(p, str)]
        patterns = [pattern] if pattern else must_contain
        if not patterns:
            return self._fail(task, validator, "pattern or must_contain required.", path=rel)
        missing = [p for p in patterns if not regex_search(p, text)]
        if not missing:
            return self._pass(task, validator, "Log contains required pattern(s).", path=rel, evidence_acceptance=f"{len(patterns)} pattern(s) matched")
        return self._fail(task, validator, f"Log missing required pattern(s): {missing}", path=rel)

    def _validate_log_not_contains_regex(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        pattern = str(validator.get("pattern") or "")
        must_not = [str(p) for p in as_list(validator.get("must_not_contain")) if isinstance(p, str)]
        patterns = [pattern] if pattern else must_not
        if not patterns:
            return self._fail(task, validator, "pattern or must_not_contain required.", path=rel)
        present = [p for p in patterns if regex_search(p, text)]
        if not present:
            return self._pass(task, validator, "Log does not contain forbidden pattern(s).", path=rel, evidence_acceptance=f"{len(patterns)} forbidden pattern(s) absent")
        return self._fail(task, validator, f"Log contains forbidden pattern(s): {present}", path=rel)

    def _validate_pytest_collected_tests(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        lower = text.lower()
        if "no tests collected" in lower:
            return self._fail(task, validator, "Pytest log says no tests collected.", path=rel, repair_instruction="Fix pytest command/test discovery or mark tests PARTIAL honestly.")
        collected = self._extract_pytest_collected_count(text)
        min_count = int(validator.get("min_count") or 1)
        if collected is not None and collected >= min_count:
            return self._pass(task, validator, f"Pytest collected {collected} tests.", path=rel, evidence_acceptance=f"collected >= {min_count}")
        if re.search(r"\b\d+\s+passed\b", lower):
            return self._pass(task, validator, "Pytest log shows passed tests.", path=rel, evidence_acceptance="passed tests pattern found")
        return self._fail(task, validator, "Pytest collection/pass evidence not found.", path=rel)

    @staticmethod
    def _extract_pytest_collected_count(text: str) -> Optional[int]:
        patterns = [
            r"collected\s+(\d+)\s+items?",
            r"collected\s+(\d+)\s+tests?",
            r"(\d+)\s+tests?\s+collected",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _validate_curl_status_check(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        code = int(validator.get("expected_status_code") or 0)
        if not code:
            return self._fail(task, validator, "expected_status_code is required.", path=rel)
        patterns = [
            rf"HTTP/[0-9.]+\s+{code}\b",
            rf"\bstatus[_ -]?code['\"]?\s*[:=]\s*{code}\b",
            rf"\bHTTP\s*{code}\b",
            rf"\b{code}\s+(OK|Created|Unauthorized|Forbidden|Not Found|Internal Server Error)\b",
            rf"→\s*HTTP\s*{code}\b",
        ]
        if any(regex_search(pattern, text) for pattern in patterns):
            return self._pass(task, validator, f"Curl/status evidence contains HTTP {code}.", path=rel, evidence_acceptance=f"HTTP {code} found")
        return self._fail(task, validator, f"Expected HTTP {code} not found in evidence log.", path=rel)

    def _validate_command_exit_code(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        code = int(validator.get("expected_exit_code") or 0)
        patterns = [
            rf"\bexit[_ -]?code\s*[:=]\s*{code}\b",
            rf"\bEXIT CODE\s*[:=]\s*{code}\b",
            rf"\breturncode\s*[:=]\s*{code}\b",
        ]
        if any(regex_search(pattern, text) for pattern in patterns):
            return self._pass(task, validator, f"Command exit code evidence found: {code}.", path=rel, evidence_acceptance=f"exit code {code} found")
        return self._fail(task, validator, f"Expected exit code {code} not found in log.", path=rel)

    # ---------------------------------------------------------------------
    # Screenshot validators
    # ---------------------------------------------------------------------

    def _validate_screenshot_exists(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, path = self._repo_path(validator)
        if not path.exists() or not path.is_file():
            return self._fail(task, validator, "Screenshot missing.", path=rel)
        min_size = int(validator.get("min_size_bytes") or 1)
        size = path.stat().st_size
        if size < min_size:
            return self._fail(task, validator, f"Screenshot too small: {size} bytes; expected >= {min_size}.", path=rel)
        if path.suffix.lower() == ".png":
            raw = path.read_bytes()[:8]
            if raw != b"\x89PNG\r\n\x1a\n":
                return self._fail(task, validator, "Screenshot is not a valid PNG file.", path=rel)
        return self._pass(task, validator, f"Screenshot exists: {size} bytes.", path=rel, evidence_acceptance=f"screenshot exists and size >= {min_size}")

    def _validate_screenshot_non_blank(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        # Without third-party image libraries, this performs a conservative
        # non-blank proxy: valid file + minimum size + byte diversity.
        rel, path = self._repo_path(validator)
        if not path.exists() or not path.is_file():
            return self._fail(task, validator, "Screenshot missing.", path=rel)
        min_size = int(validator.get("min_size_bytes") or 5_000)
        raw = path.read_bytes()
        if len(raw) < min_size:
            return self._fail(task, validator, f"Screenshot too small for non-blank proof: {len(raw)} bytes; expected >= {min_size}.", path=rel)
        diversity = len(set(raw[: min(len(raw), 100_000)]))
        if diversity < 16:
            return self._fail(task, validator, f"Screenshot has low byte diversity: {diversity}.", path=rel)
        return self._pass(
            task,
            validator,
            f"Screenshot passes basic non-blank proxy: size={len(raw)}, diversity={diversity}.",
            path=rel,
            evidence_acceptance="valid screenshot file with minimum size and byte diversity; manual visual review still required",
            details={"byte_diversity_sample": diversity},
        )

    # ---------------------------------------------------------------------
    # JSON / forbidden / allowed changed validators
    # ---------------------------------------------------------------------

    def _validate_json_path_equals(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, path = self._repo_path(validator)
        if not path.exists():
            return self._fail(task, validator, "JSON file missing.", path=rel)
        data = json.loads(read_text_file(path))
        json_path = str(validator.get("json_path") or "")
        expected = validator.get("expected_value")
        if not json_path:
            return self._fail(task, validator, "json_path is required.", path=rel)
        actual = self._resolve_simple_json_path(data, json_path)
        if actual == expected:
            return self._pass(task, validator, f"JSON path equals expected value: {json_path}", path=rel, evidence_acceptance="JSON path exact match")
        return self._fail(task, validator, f"JSON path mismatch for {json_path}: actual={actual!r}, expected={expected!r}", path=rel)

    @staticmethod
    def _resolve_simple_json_path(data: Any, path: str) -> Any:
        # Supports $.a.b[0].c and a.b style. No full JSONPath dependency.
        value = data
        clean = path[2:] if path.startswith("$.") else path
        tokens = re.findall(r"([A-Za-z0-9_\-]+)|\[(\d+)\]", clean)
        for key, index in tokens:
            if key:
                if not isinstance(value, Mapping):
                    return None
                value = value.get(key)
            else:
                if not isinstance(value, list):
                    return None
                idx = int(index)
                if idx >= len(value):
                    return None
                value = value[idx]
        return value

    def _validate_forbidden_code_check(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        rel, text = self._read_validator_text(validator)
        patterns = [str(p) for p in as_list(validator.get("patterns")) if isinstance(p, str)]
        if not patterns:
            patterns = list(FORBIDDEN_DEFAULT_PATTERNS_BEFORE_PR08)
        matches = [p for p in patterns if regex_search(p, text)]
        if not matches:
            return self._pass(task, validator, "No forbidden code pattern found.", path=rel, evidence_acceptance=f"{len(patterns)} forbidden pattern(s) absent")
        return self._fail(
            task,
            validator,
            f"Forbidden code pattern(s) found: {matches}",
            path=rel,
            repair_instruction="Remove paid/cloud/external production integration or replace with local/free/mock adapter before PR.08.",
        )

    def _validate_allowed_files_changed_only(self, task: Mapping[str, Any], validator: Mapping[str, Any]) -> ValidatorOutcome:
        allowed = self._task_allowed_edit_files(task)
        changed = self._changed_files_from_contract()
        task_id = str(task.get("task_id") or "")
        task_changed = {
            path for path, task_ids in changed.items()
            if not task_ids or task_id in task_ids
        }
        unexpected = sorted(path for path in task_changed if path not in allowed)
        if not unexpected:
            return self._pass(task, validator, "Changed files are within allowed edit set.", evidence_acceptance=f"{len(task_changed)} changed file(s) checked")
        return self._fail(
            task,
            validator,
            f"Task changed files outside allowed edit set: {unexpected}",
            details={"allowed_edit_files": sorted(allowed), "changed_files": sorted(task_changed)},
            repair_instruction="Revert or justify out-of-scope edits. If extra files are required, add requested_extra_files and get approval before editing.",
        )

    def _task_allowed_edit_files(self, task: Mapping[str, Any]) -> Set[str]:
        allowed_files = task.get("allowed_files") or {}
        paths = set()
        for path in as_list(allowed_files.get("edit")):
            if isinstance(path, str):
                paths.add(normalize_rel_path(path))
        return paths

    def _changed_files_from_contract(self) -> Dict[str, Set[str]]:
        changed: Dict[str, Set[str]] = {}
        for item in as_list(dict_get(self.contract, "kimchi_updates", "changed_files")):
            if isinstance(item, Mapping) and isinstance(item.get("path"), str):
                path = normalize_rel_path(item["path"])
                task_ids = {str(t) for t in as_list(item.get("task_ids")) if isinstance(t, str)}
                changed[path] = task_ids
        return changed

    # ---------------------------------------------------------------------
    # Report / next action
    # ---------------------------------------------------------------------

    def _build_report(self, overall_status: str, task_results: Sequence[TaskResult]) -> Dict[str, Any]:
        task_payloads = []
        all_outcomes: List[ValidatorOutcome] = []
        for task_result in task_results:
            all_outcomes.extend(task_result.outcomes)
            task_payloads.append(
                {
                    "task_id": task_result.task_id,
                    "scope_id": task_result.scope_id,
                    "title": task_result.title,
                    "sequence": task_result.sequence,
                    "status": task_result.status,
                    "passed_count": task_result.passed_count,
                    "failed_count": task_result.failed_count,
                    "manual_review_required_count": task_result.manual_review_required_count,
                    "outcomes": [dataclasses.asdict(o) for o in task_result.outcomes],
                }
            )

        failed = [o for o in all_outcomes if o.status != STATUS_PASS and not o.manual_review_required]
        manual = [o for o in all_outcomes if o.manual_review_required]
        next_action = self._next_action(overall_status, task_results)
        cost_control_for_followup = self._cost_control_for_followup(next_action)
        kimchi_next_prompt = self._kimchi_next_prompt(overall_status, next_action, cost_control_for_followup)

        return {
            "generated_by": "stage_completion_validator.py",
            "generated_at": utc_now_iso(),
            "status": overall_status,
            "contract_id": self.contract.get("contract_id"),
            "stage_id": dict_get(self.contract, "stage", "stage_id"),
            "stage_title": dict_get(self.contract, "stage", "stage_title"),
            "repo_root": str(self.repo_root),
            "contract_path": self.contract_rel_path or str(self.contract_path),
            "zip_path": str(self.zip.zip_path) if self.zip.zip_path else None,
            "report_path": self._report_rel_or_abs(),
            "counts": {
                "tasks": len(task_results),
                "tasks_pass": len([t for t in task_results if t.status == STATUS_PASS]),
                "tasks_partial": len([t for t in task_results if t.status == STATUS_PARTIAL]),
                "tasks_no_go": len([t for t in task_results if t.status == STATUS_NO_GO]),
                "validators": len(all_outcomes),
                "validators_pass": len([o for o in all_outcomes if o.status == STATUS_PASS]),
                "validators_failed": len(failed),
                "manual_review_required": len(manual),
            },
            "task_results": task_payloads,
            "failed_validators": [dataclasses.asdict(o) for o in failed],
            "manual_review_required": [dataclasses.asdict(o) for o in manual],
            "next_action": next_action,
            "cost_control_for_followup": cost_control_for_followup,
            "kimchi_next_prompt": kimchi_next_prompt,
        }

    def _report_rel_or_abs(self) -> str:
        try:
            return self.report_out.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return str(self.report_out)

    def _next_action(self, overall_status: str, task_results: Sequence[TaskResult]) -> Dict[str, Any]:
        if overall_status == STATUS_PASS:
            return {
                "action_type": "manual_review",
                "title": "All mechanical task validators passed; proceed to manual source/evidence review.",
                "task_id": None,
                "scope_id": None,
                "allowed_files": {"read": [], "edit": [], "include_in_zip": [], "evidence": [], "screenshots": []},
                "instructions": [
                    "Do not accept from validator status alone.",
                    "Manually read changed source/config/test files end-to-end.",
                    "Inspect screenshots for actual loaded UI and claimed behavior.",
                    "Review raw logs for command status and content.",
                ],
            }

        failed_tasks = [t for t in task_results if t.status in {STATUS_NO_GO, STATUS_PARTIAL, STATUS_NOT_RUN}]
        failed_tasks.sort(key=lambda t: (0 if t.status == STATUS_NO_GO else 1, t.sequence))
        target = failed_tasks[0] if failed_tasks else None
        if target is None:
            return {
                "action_type": "stop",
                "title": "No failed task found but stage is not PASS.",
                "task_id": None,
                "scope_id": None,
                "allowed_files": {"read": [], "edit": [], "include_in_zip": [], "evidence": [], "screenshots": []},
                "instructions": ["Inspect validator report."],
            }

        task_dict = self._task_by_id(target.task_id)
        failed_outcomes = [o for o in target.outcomes if o.status != STATUS_PASS and not o.manual_review_required]
        primary = self._primary_outcome(failed_outcomes)
        allowed_files = task_dict.get("allowed_files") if isinstance(task_dict, Mapping) else {}

        instructions = [
            f"Fix only task {target.task_id}: {target.title}.",
            f"Primary failure: {primary.message if primary else 'unknown failure'}",
            f"Repair instruction: {primary.repair_instruction if primary else task_dict.get('repair_instruction', 'Fix failed validators only.')}",
            "Read/edit only the allowed files for this task unless a true blocker requires requested_extra_files.",
            "After fixing, rerun stage_completion_validator.py for this task first, then rerun full stage validator.",
            "Do not proceed to unrelated tasks until this task passes or is explicitly deferred.",
        ]

        return {
            "action_type": "fix_failed_task",
            "title": f"Fix {target.task_id} only",
            "task_id": target.task_id,
            "scope_id": target.scope_id,
            "allowed_files": allowed_files,
            "failed_validators": [dataclasses.asdict(o) for o in failed_outcomes],
            "instructions": instructions,
        }

    @staticmethod
    def _primary_outcome(outcomes: Sequence[ValidatorOutcome]) -> Optional[ValidatorOutcome]:
        if not outcomes:
            return None
        return sorted(outcomes, key=lambda o: (-SEVERITY_ORDER.get(o.severity, 0), o.validator_id))[0]

    def _task_by_id(self, task_id: str) -> Mapping[str, Any]:
        for task in as_list(self.contract.get("task_sequence")):
            if isinstance(task, Mapping) and task.get("task_id") == task_id:
                return task
        return {}

    def _cost_control_for_followup(self, next_action: Mapping[str, Any]) -> Dict[str, Any]:
        cost = self.contract.get("cost_control") or {}
        allowed = next_action.get("allowed_files") if isinstance(next_action.get("allowed_files"), Mapping) else {}
        return {
            "fresh_session_required": True,
            "do_not_use_old_chat_context": True,
            "do_not_use_subagents": bool(cost.get("forbid_subagents_by_default", True)),
            "do_not_do_broad_repo_scan": bool(cost.get("forbid_broad_repo_scan", True)),
            "read_only_allowed_files": True,
            "edit_only_allowed_files": True,
            "max_files_to_read_per_task": cost.get("max_files_to_read_per_task"),
            "max_files_to_edit_per_task": cost.get("max_files_to_edit_per_task"),
            "max_retries_per_task": cost.get("max_retries_per_task"),
            "stop_if_context_estimate_exceeds_tokens": cost.get("stop_if_context_estimate_exceeds_tokens"),
            "target_max_input_tokens_correction": cost.get("target_max_input_tokens_correction"),
            "output_verbosity": cost.get("output_verbosity", "concise"),
            "allowed_read_files": allowed.get("read", []),
            "allowed_edit_files": allowed.get("edit", []),
            "allowed_evidence_files": allowed.get("evidence", []),
            "allowed_screenshots": allowed.get("screenshots", []),
        }

    def _kimchi_next_prompt(
        self,
        overall_status: str,
        next_action: Mapping[str, Any],
        cost_control: Mapping[str, Any],
    ) -> str:
        if overall_status == STATUS_PASS:
            return (
                "Mechanical stage-completion validators passed. Do not continue implementation. "
                "Prepare for manual source-grounded review only."
            )

        task_id = next_action.get("task_id")
        instructions = next_action.get("instructions") or []
        allowed_read = cost_control.get("allowed_read_files") or []
        allowed_edit = cost_control.get("allowed_edit_files") or []

        lines = [
            "Fresh bounded correction. Do not use old chat context. Do not use subagents. Do not scan the broad repo.",
            f"Fix only task: {task_id}.",
            f"Read only these files: {allowed_read}",
            f"Edit only these files: {allowed_edit}",
            f"Token target: correction input <= {cost_control.get('target_max_input_tokens_correction')} tokens.",
            f"Stop if estimated context exceeds {cost_control.get('stop_if_context_estimate_exceeds_tokens')} tokens.",
            "Instructions:",
        ]
        lines.extend(f"- {item}" for item in instructions)
        lines.append("After the fix, rerun stage_completion_validator.py for this task and report only validator status plus changed files.")
        return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate BhojanGo task-level stage completion from a stage contract.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--contract", required=True, help="Repo-relative or absolute path to stage contract JSON.")
    parser.add_argument("--repo-root", default=None, help="Repo root. Defaults to nearest parent with package.json and pnpm-workspace.yaml.")
    parser.add_argument("--zip", dest="zip_override", default=None, help="Optional review zip override.")
    parser.add_argument("--report-out", default=None, help="Optional validator report JSON output path.")
    parser.add_argument("--task", default=None, help="Optional single task_id to validate.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress.")
    return parser.parse_args(argv)


def resolve_config(args: argparse.Namespace) -> ValidatorConfig:
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else infer_repo_root(Path.cwd())

    contract_arg = Path(args.contract).expanduser()
    contract_path = contract_arg.resolve() if contract_arg.is_absolute() else (repo_root / contract_arg).resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        raise CompletionValidatorError(f"Repo root is not a directory: {repo_root}")
    if not contract_path.exists() or not contract_path.is_file():
        raise CompletionValidatorError(f"Contract file is not found: {contract_path}")

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
        task_filter=args.task,
        zip_override=zip_override,
        report_out=report_out,
        verbose=bool(args.verbose),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        config = resolve_config(args)
        validator = StageCompletionValidator(config)
        status, report = validator.validate()

        summary = {
            "status": status,
            "contract_id": report.get("contract_id"),
            "stage_id": report.get("stage_id"),
            "report_path": report.get("report_path"),
            "tasks": report.get("counts", {}).get("tasks"),
            "tasks_pass": report.get("counts", {}).get("tasks_pass"),
            "tasks_partial": report.get("counts", {}).get("tasks_partial"),
            "tasks_no_go": report.get("counts", {}).get("tasks_no_go"),
            "validators_failed": report.get("counts", {}).get("validators_failed"),
            "manual_review_required": report.get("counts", {}).get("manual_review_required"),
            "next_action": report.get("next_action", {}).get("title"),
            "next_task": report.get("next_action", {}).get("task_id"),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        return 0 if status == STATUS_PASS else 1

    except CompletionValidatorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: interrupted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
