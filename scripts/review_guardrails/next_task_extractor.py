#!/usr/bin/env python3
"""
next_task_extractor.py

Small-context correction extractor for BhojanGo guardrail-driven workflows.

Purpose
-------
Kimchi should not repeatedly read the full stage contract, policy, full validator
reports, or old chat context during correction loops. This script reads the
contract and validator reports, then writes a tiny next_task.json work order.

The output is intentionally small and bounded:
- one next action only
- one task_id, if applicable
- allowed read/edit/evidence/screenshot files only for that task/action
- compact failed validator summaries
- cost-control limits copied from the contract
- a copy-paste kimchi_next_prompt that avoids broad context

This script does not validate source behavior. It extracts the smallest safe
follow-up from existing validator results.

Typical usage
-------------
From repo root:

    python scripts/review_guardrails/next_task_extractor.py \
      --contract review_contracts/SPR-02-v3.contract.json

Optional:

    python scripts/review_guardrails/next_task_extractor.py \
      --contract review_contracts/SPR-02-v3.contract.json \
      --max-failures 3

Outputs
-------
Default:

    tests/results/evidence/validator_outputs/next_task.json
    tests/results/evidence/validator_outputs/next_task_prompt.txt

Exit codes
----------
0 = next_task generated
1 = next_task generated but action is non-PASS / correction needed
2 = invalid arguments / missing contract
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL"
STATUS_NO_GO = "NO-GO"

DEFAULT_REPO_MARKERS = ("package.json", "pnpm-workspace.yaml")

DEFAULT_OUTPUT_JSON = "tests/results/evidence/validator_outputs/next_task.json"
DEFAULT_OUTPUT_PROMPT = "tests/results/evidence/validator_outputs/next_task_prompt.txt"

DEFAULT_GUARDRAIL_FILES = [
    "scripts/review_guardrails/stage_contract.schema.json",
    "scripts/review_guardrails/stage_packager.py",
    "scripts/review_guardrails/review_export_validator.py",
    "scripts/review_guardrails/stage_completion_validator.py",
    "scripts/review_guardrails/next_task_extractor.py",
    "docs/review_export_policy.md",
]


class ExtractorError(Exception):
    """Fatal extractor error."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExtractorError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExtractorError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def dict_get(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    node: Any = mapping
    for key in keys:
        if not isinstance(node, Mapping):
            return default
        node = node.get(key)
    return default if node is None else node


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


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
        raise ExtractorError(f"Invalid repo-relative path: {raw!r}")
    return value


def safe_rel_to_path(repo_root: Path, rel_path: str) -> Path:
    rel = normalize_rel_path(rel_path)
    candidate = (repo_root / rel).resolve()
    root = repo_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ExtractorError(f"Path escapes repo root: {rel_path}") from exc
    return candidate


def infer_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if all((candidate / marker).exists() for marker in DEFAULT_REPO_MARKERS):
            return candidate
    return current


def rel_or_abs(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def file_sha256(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 20].rstrip() + "...<truncated>"


def unique_paths(paths: Iterable[Any]) -> List[str]:
    output: List[str] = []
    seen = set()
    for path in paths:
        if not isinstance(path, str) or not path.strip():
            continue
        rel = normalize_rel_path(path)
        if rel not in seen:
            output.append(rel)
            seen.add(rel)
    return output


class NextTaskExtractor:
    """Generate tiny next_task work order from contract + validator outputs."""

    def __init__(
        self,
        *,
        repo_root: Path,
        contract_path: Path,
        output_json: Path,
        output_prompt: Path,
        max_failures: int,
        max_chars_per_failure: int,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.contract_path = contract_path.resolve()
        self.contract = load_json(self.contract_path)
        self.output_json = output_json.resolve()
        self.output_prompt = output_prompt.resolve()
        self.max_failures = max_failures
        self.max_chars_per_failure = max_chars_per_failure

        self.contract_id = str(self.contract.get("contract_id") or "UNKNOWN_CONTRACT")
        self.stage_id = str(dict_get(self.contract, "stage", "stage_id", default="UNKNOWN_STAGE"))

    def run(self) -> Tuple[int, Dict[str, Any]]:
        packager_report = self._load_report("packager")
        review_report = self._load_report("review_export")
        completion_report = self._load_report("stage_completion")

        payload = self._build_next_task(packager_report, review_report, completion_report)

        write_json(self.output_json, payload)
        write_text(self.output_prompt, payload["kimchi_next_prompt"])

        if payload["decision"]["overall_action"] in {"manual_review", "stop_no_action"}:
            return 0, payload
        return 1, payload

    def _load_report(self, report_type: str) -> Optional[Dict[str, Any]]:
        path = self._report_path(report_type)
        if not path.exists():
            return None
        return load_json(path)

    def _report_path(self, report_type: str) -> Path:
        if report_type == "packager":
            rel = f"tests/results/evidence/validator_outputs/{self.contract_id}_packager_report.json"
        elif report_type == "review_export":
            rel = f"tests/results/evidence/validator_outputs/{self.contract_id}_review_export_validation.json"
        elif report_type == "stage_completion":
            rel = f"tests/results/evidence/validator_outputs/{self.contract_id}_stage_completion_validation.json"
        else:
            raise ExtractorError(f"Unknown report type: {report_type}")
        return safe_rel_to_path(self.repo_root, rel)

    def _build_next_task(
        self,
        packager_report: Optional[Mapping[str, Any]],
        review_report: Optional[Mapping[str, Any]],
        completion_report: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        report_statuses = {
            "packager": self._status_or_missing(packager_report),
            "review_export": self._status_or_missing(review_report),
            "stage_completion": self._status_or_missing(completion_report),
        }

        decision = self._choose_decision(packager_report, review_report, completion_report)
        allowed_files = self._allowed_files_for_decision(decision)
        failures = self._compact_failures_for_decision(decision, packager_report, review_report, completion_report)
        cost_control = self._cost_control_for_followup(allowed_files)
        guardrail_freeze = self._guardrail_freeze_snapshot()
        prompt = self._build_kimchi_prompt(decision, allowed_files, failures, cost_control)

        return {
            "generated_by": "next_task_extractor.py",
            "generated_at": utc_now_iso(),
            "contract_id": self.contract_id,
            "stage_id": self.stage_id,
            "contract_path": rel_or_abs(self.contract_path, self.repo_root),
            "report_statuses": report_statuses,
            "decision": decision,
            "allowed_files": allowed_files,
            "compact_failures": failures,
            "cost_control_for_followup": cost_control,
            "guardrail_freeze_snapshot": guardrail_freeze,
            "kimchi_next_prompt": prompt,
            "usage_rule": {
                "kimchi_should_read_this_file_only_first": rel_or_abs(self.output_json, self.repo_root),
                "do_not_read_full_contract_unless_next_task_requires_it": True,
                "do_not_read_full_validator_reports_unless_specific_failure_says_to": True,
                "do_not_use_old_chat_context": True,
                "do_not_use_subagents": True,
                "do_not_scan_broad_repo": True,
            },
        }

    @staticmethod
    def _status_or_missing(report: Optional[Mapping[str, Any]]) -> str:
        if report is None:
            return "MISSING"
        return str(report.get("status") or "UNKNOWN")

    def _choose_decision(
        self,
        packager_report: Optional[Mapping[str, Any]],
        review_report: Optional[Mapping[str, Any]],
        completion_report: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        # Report priority:
        # 1) packager missing/fail: packaging must be fixed before export validation.
        # 2) review export missing/fail: package/evidence consistency must be fixed.
        # 3) stage completion missing/fail: fix exact failed task.
        # 4) all pass: manual review only.
        if packager_report is None:
            return self._packaging_decision("packager_missing", "Run stage_packager.py first; packager report is missing.")
        if str(packager_report.get("status")) != STATUS_PASS:
            return self._packaging_decision("packager_not_pass", "Fix packager failures first.", packager_report)

        if review_report is None:
            return self._packaging_decision("review_export_validator_missing", "Run review_export_validator.py; review export report is missing.")
        if str(review_report.get("status")) != STATUS_PASS:
            return self._review_export_decision(review_report)

        if completion_report is None:
            return self._stage_completion_decision_missing()
        if str(completion_report.get("status")) != STATUS_PASS:
            return self._stage_completion_decision(completion_report)

        return {
            "overall_action": "manual_review",
            "reason": "packager, review_export_validator, and stage_completion_validator all report PASS.",
            "task_id": None,
            "scope_id": None,
            "title": "Mechanical validators passed; proceed to manual source/evidence review.",
            "command_to_run_first": None,
            "stop_after_action": True,
        }

    def _packaging_decision(
        self,
        reason_code: str,
        title: str,
        report: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "overall_action": "fix_packaging",
            "reason": reason_code,
            "task_id": None,
            "scope_id": None,
            "title": title,
            "command_to_run_first": "python scripts/review_guardrails/stage_packager.py --contract review_contracts/SPR-02-v3.contract.json --clean",
            "stop_after_action": True,
            "next_action_from_report": (report or {}).get("next_action"),
        }

    def _review_export_decision(self, review_report: Mapping[str, Any]) -> Dict[str, Any]:
        next_action = review_report.get("next_action") if isinstance(review_report.get("next_action"), Mapping) else {}
        return {
            "overall_action": "fix_review_export",
            "reason": "review_export_validator_not_pass",
            "task_id": None,
            "scope_id": None,
            "title": str(next_action.get("title") or "Fix review export packaging/evidence."),
            "command_to_run_first": "python scripts/review_guardrails/review_export_validator.py --contract review_contracts/SPR-02-v3.contract.json",
            "stop_after_action": True,
            "next_action_from_report": next_action,
        }

    def _stage_completion_decision_missing(self) -> Dict[str, Any]:
        return {
            "overall_action": "run_stage_completion_validator",
            "reason": "stage_completion_validator_missing",
            "task_id": None,
            "scope_id": None,
            "title": "Run stage_completion_validator.py; stage completion report is missing.",
            "command_to_run_first": "python scripts/review_guardrails/stage_completion_validator.py --contract review_contracts/SPR-02-v3.contract.json",
            "stop_after_action": True,
        }

    def _stage_completion_decision(self, completion_report: Mapping[str, Any]) -> Dict[str, Any]:
        next_action = completion_report.get("next_action") if isinstance(completion_report.get("next_action"), Mapping) else {}
        task_id = next_action.get("task_id")
        task = self._task_by_id(str(task_id)) if task_id else {}
        scope_id = next_action.get("scope_id") or task.get("scope_id")
        return {
            "overall_action": "fix_failed_task",
            "reason": "stage_completion_validator_not_pass",
            "task_id": task_id,
            "scope_id": scope_id,
            "title": str(next_action.get("title") or f"Fix {task_id} only"),
            "command_to_run_first": f"python scripts/review_guardrails/stage_completion_validator.py --contract review_contracts/SPR-02-v3.contract.json --task {task_id}" if task_id else None,
            "stop_after_action": True,
            "next_action_from_report": next_action,
        }

    def _task_by_id(self, task_id: str) -> Mapping[str, Any]:
        for task in as_list(self.contract.get("task_sequence")):
            if isinstance(task, Mapping) and task.get("task_id") == task_id:
                return task
        return {}

    def _allowed_files_for_decision(self, decision: Mapping[str, Any]) -> Dict[str, List[str]]:
        action = decision.get("overall_action")
        if action == "fix_failed_task" and decision.get("task_id"):
            task = self._task_by_id(str(decision["task_id"]))
            file_set = task.get("allowed_files") if isinstance(task, Mapping) else {}
            return self._normalize_file_set(file_set)

        if action in {"fix_packaging", "fix_review_export", "run_stage_completion_validator"}:
            # Packaging corrections can read guardrails, contract, and generated validator reports.
            read_paths = [
                "review_contracts/SPR-02-v3.contract.json",
                *DEFAULT_GUARDRAIL_FILES,
                f"tests/results/evidence/validator_outputs/{self.contract_id}_packager_report.json",
                f"tests/results/evidence/validator_outputs/{self.contract_id}_review_export_validation.json",
                f"tests/results/evidence/validator_outputs/{self.contract_id}_stage_completion_validation.json",
            ]
            edit_paths = [
                "review_contracts/SPR-02-v3.contract.json",
                f"tests/results/evidence/validator_outputs/{self.contract_id}_packager_report.json",
                f"tests/results/evidence/validator_outputs/{self.contract_id}_review_export_validation.json",
                f"tests/results/evidence/validator_outputs/{self.contract_id}_stage_completion_validation.json",
                "tests/results/evidence/logs/spr02-v3-zip-listing.log",
            ]
            return {
                "read": unique_paths(read_paths),
                "edit": unique_paths(edit_paths),
                "include_in_zip": unique_paths(read_paths + edit_paths),
                "evidence": unique_paths(edit_paths),
                "screenshots": [],
            }

        return {"read": [], "edit": [], "include_in_zip": [], "evidence": [], "screenshots": []}

    def _normalize_file_set(self, file_set: Any) -> Dict[str, List[str]]:
        if not isinstance(file_set, Mapping):
            return {"read": [], "edit": [], "include_in_zip": [], "evidence": [], "screenshots": []}
        return {
            "read": unique_paths(file_set.get("read") or []),
            "edit": unique_paths(file_set.get("edit") or []),
            "include_in_zip": unique_paths(file_set.get("include_in_zip") or []),
            "evidence": unique_paths(file_set.get("evidence") or []),
            "screenshots": unique_paths(file_set.get("screenshots") or []),
        }

    def _compact_failures_for_decision(
        self,
        decision: Mapping[str, Any],
        packager_report: Optional[Mapping[str, Any]],
        review_report: Optional[Mapping[str, Any]],
        completion_report: Optional[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        action = decision.get("overall_action")
        if action == "fix_packaging":
            return self._compact_packager_failures(packager_report)
        if action == "fix_review_export":
            return self._compact_review_failures(review_report)
        if action == "fix_failed_task":
            return self._compact_completion_failures(completion_report, str(decision.get("task_id") or ""))
        return []

    def _compact_packager_failures(self, report: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        if report is None:
            return [{
                "source_report": "packager",
                "code": "PACKAGER_REPORT_MISSING",
                "severity": "BLOCKER",
                "path": None,
                "message": "Packager report is missing.",
                "repair_instruction": "Run stage_packager.py with --clean.",
            }]
        failures = []
        for key in ("missing_required", "forbidden_paths", "copy_errors", "required_missing_from_zip"):
            for item in as_list(report.get(key)):
                failures.append({
                    "source_report": "packager",
                    "code": key,
                    "severity": "BLOCKER",
                    "path": item.get("path") if isinstance(item, Mapping) else item,
                    "message": truncate(json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item, self.max_chars_per_failure),
                    "repair_instruction": "Fix packager issue only; do not broaden app implementation.",
                })
        return failures[: self.max_failures]

    def _compact_review_failures(self, report: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        if report is None:
            return [{
                "source_report": "review_export_validator",
                "code": "REVIEW_EXPORT_REPORT_MISSING",
                "severity": "BLOCKER",
                "path": None,
                "message": "Review export validation report is missing.",
                "repair_instruction": "Run review_export_validator.py.",
            }]
        failures = []
        for item in as_list(report.get("findings")):
            if not isinstance(item, Mapping):
                continue
            failures.append({
                "source_report": "review_export_validator",
                "code": item.get("code"),
                "severity": item.get("severity"),
                "path": item.get("path"),
                "message": truncate(str(item.get("message") or ""), self.max_chars_per_failure),
                "repair_instruction": truncate(str(item.get("repair_instruction") or "Fix this review export issue only."), self.max_chars_per_failure),
            })
        return failures[: self.max_failures]

    def _compact_completion_failures(self, report: Optional[Mapping[str, Any]], task_id: str) -> List[Dict[str, Any]]:
        if report is None:
            return [{
                "source_report": "stage_completion_validator",
                "task_id": task_id,
                "validator_id": None,
                "severity": "BLOCKER",
                "path": None,
                "message": "Stage completion report is missing.",
                "repair_instruction": "Run stage_completion_validator.py.",
            }]
        failures = []
        for item in as_list(report.get("failed_validators")):
            if not isinstance(item, Mapping):
                continue
            if task_id and item.get("task_id") != task_id:
                continue
            failures.append({
                "source_report": "stage_completion_validator",
                "task_id": item.get("task_id"),
                "scope_id": item.get("scope_id"),
                "validator_id": item.get("validator_id"),
                "validator_type": item.get("validator_type"),
                "severity": item.get("severity"),
                "path": item.get("path"),
                "message": truncate(str(item.get("message") or ""), self.max_chars_per_failure),
                "repair_instruction": truncate(str(item.get("repair_instruction") or "Fix this failed validator only."), self.max_chars_per_failure),
            })
        return failures[: self.max_failures]

    def _cost_control_for_followup(self, allowed_files: Mapping[str, List[str]]) -> Dict[str, Any]:
        cost = self.contract.get("cost_control") or {}
        return {
            "fresh_session_required": True,
            "do_not_use_old_chat_context": True,
            "do_not_use_subagents": bool(cost.get("forbid_subagents_by_default", True)),
            "do_not_do_broad_repo_scan": bool(cost.get("forbid_broad_repo_scan", True)),
            "read_only_allowed_files": True,
            "edit_only_allowed_files": True,
            "max_files_to_read_per_task": cost.get("max_files_to_read_per_task", 8),
            "max_files_to_edit_per_task": cost.get("max_files_to_edit_per_task", 4),
            "max_retries_per_task": cost.get("max_retries_per_task", 2),
            "stop_if_context_estimate_exceeds_tokens": cost.get("stop_if_context_estimate_exceeds_tokens", 75000),
            "target_max_input_tokens_correction": cost.get("target_max_input_tokens_correction", 1000000),
            "hard_max_tool_calls_for_next_correction": 12,
            "hard_max_read_calls_for_next_correction": 4,
            "hard_max_bash_calls_for_next_correction": 6,
            "output_verbosity": cost.get("output_verbosity", "concise"),
            "allowed_read_files": allowed_files.get("read", []),
            "allowed_edit_files": allowed_files.get("edit", []),
        }

    def _guardrail_freeze_snapshot(self) -> Dict[str, Any]:
        files = []
        for rel in DEFAULT_GUARDRAIL_FILES:
            path = safe_rel_to_path(self.repo_root, rel)
            files.append({
                "path": rel,
                "exists": path.exists(),
                "sha256": file_sha256(path),
            })
        return {
            "purpose": "Use this snapshot to detect whether Kimchi edited guardrail files during app-stage work.",
            "rule": "Guardrail script changes during app implementation require explicit user approval; otherwise treat as NO-GO or separate guardrail-fix task.",
            "files": files,
        }

    def _build_kimchi_prompt(
        self,
        decision: Mapping[str, Any],
        allowed_files: Mapping[str, List[str]],
        failures: Sequence[Mapping[str, Any]],
        cost_control: Mapping[str, Any],
    ) -> str:
        action = decision.get("overall_action")
        if action == "manual_review":
            return (
                "Mechanical validators passed. Stop implementation. Do not continue to edit files. "
                "Prepare only for manual source/evidence review."
            )

        lines = [
            "Fresh bounded correction. Do not use old chat context. Do not use subagents. Do not scan the broad repo.",
            f"Stage: {self.stage_id}. Contract: review_contracts/SPR-02-v3.contract.json.",
            f"Action: {action}.",
            f"Task ID: {decision.get('task_id')}.",
            f"Scope ID: {decision.get('scope_id')}.",
            f"Title: {decision.get('title')}.",
            "",
            "Cost controls:",
            f"- Target correction input <= {cost_control.get('target_max_input_tokens_correction')} tokens.",
            f"- Stop if estimated context exceeds {cost_control.get('stop_if_context_estimate_exceeds_tokens')} tokens.",
            f"- Max read calls: {cost_control.get('hard_max_read_calls_for_next_correction')}.",
            f"- Max bash calls: {cost_control.get('hard_max_bash_calls_for_next_correction')}.",
            f"- Max total tool calls: {cost_control.get('hard_max_tool_calls_for_next_correction')}.",
            "",
            f"Read only: {allowed_files.get('read', [])}",
            f"Edit only: {allowed_files.get('edit', [])}",
            f"Evidence files: {allowed_files.get('evidence', [])}",
            f"Screenshots: {allowed_files.get('screenshots', [])}",
            "",
            "Failures to fix:",
        ]

        if failures:
            for idx, failure in enumerate(failures, 1):
                lines.append(
                    f"{idx}. {failure.get('code') or failure.get('validator_id')} | "
                    f"path={failure.get('path')} | {failure.get('message')} | "
                    f"repair={failure.get('repair_instruction')}"
                )
        else:
            lines.append("No compact failures found. Run the command below and inspect only the generated next_action.")

        if decision.get("command_to_run_first"):
            lines.extend(["", f"Run first: {decision.get('command_to_run_first')}"])

        if decision.get("task_id"):
            lines.extend([
                "",
                "After the fix, run only this task validator first:",
                f"python scripts/review_guardrails/stage_completion_validator.py --contract review_contracts/SPR-02-v3.contract.json --task {decision.get('task_id')}",
            ])

        lines.extend([
            "",
            "Then regenerate next_task.json:",
            "python scripts/review_guardrails/next_task_extractor.py --contract review_contracts/SPR-02-v3.contract.json",
            "",
            "Report only: status, changed files, validator path, remaining failed task ID. Do not write a broad narrative.",
        ])

        return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a tiny next-task work order from BhojanGo validator outputs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--contract", required=True, help="Repo-relative or absolute stage contract JSON path.")
    parser.add_argument("--repo-root", default=None, help="Repo root. Defaults to nearest parent with package.json and pnpm-workspace.yaml.")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON, help="Output next_task JSON path.")
    parser.add_argument("--output-prompt", default=DEFAULT_OUTPUT_PROMPT, help="Output compact Kimchi prompt text path.")
    parser.add_argument("--max-failures", type=int, default=5, help="Maximum failures to include in next_task.json.")
    parser.add_argument("--max-chars-per-failure", type=int, default=600, help="Maximum characters per compact failure field.")
    return parser.parse_args(argv)


def resolve_config(args: argparse.Namespace) -> Tuple[Path, Path, Path, Path]:
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else infer_repo_root(Path.cwd())
    contract_arg = Path(args.contract).expanduser()
    contract_path = contract_arg.resolve() if contract_arg.is_absolute() else (repo_root / contract_arg).resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        raise ExtractorError(f"Repo root is not a directory: {repo_root}")
    if not contract_path.exists() or not contract_path.is_file():
        raise ExtractorError(f"Contract file is not found: {contract_path}")

    output_json_arg = Path(args.output_json).expanduser()
    output_json = output_json_arg.resolve() if output_json_arg.is_absolute() else (repo_root / output_json_arg).resolve()

    output_prompt_arg = Path(args.output_prompt).expanduser()
    output_prompt = output_prompt_arg.resolve() if output_prompt_arg.is_absolute() else (repo_root / output_prompt_arg).resolve()

    return repo_root, contract_path, output_json, output_prompt


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        repo_root, contract_path, output_json, output_prompt = resolve_config(args)

        extractor = NextTaskExtractor(
            repo_root=repo_root,
            contract_path=contract_path,
            output_json=output_json,
            output_prompt=output_prompt,
            max_failures=max(1, args.max_failures),
            max_chars_per_failure=max(120, args.max_chars_per_failure),
        )
        exit_code, payload = extractor.run()

        summary = {
            "status": "PASS" if exit_code == 0 else "ACTION_REQUIRED",
            "contract_id": payload.get("contract_id"),
            "stage_id": payload.get("stage_id"),
            "overall_action": payload.get("decision", {}).get("overall_action"),
            "task_id": payload.get("decision", {}).get("task_id"),
            "output_json": rel_or_abs(output_json, repo_root),
            "output_prompt": rel_or_abs(output_prompt, repo_root),
            "report_statuses": payload.get("report_statuses"),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return exit_code

    except ExtractorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: interrupted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
