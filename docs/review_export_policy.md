# BhojanGo Review Export Policy

## 1. Purpose

This policy defines how every BhojanGo stage implementation, correction, validation, and review-export package must be prepared.

The goal is to prevent repeated failure modes:

- evidence-only or Markdown-only review zips
- missing backend/frontend/test/source files
- false file-read ledger claims
- flattened `changed/` or `reference/` folders
- missing screenshots or screenshots showing skeleton/loading states
- logs that do not prove the claimed behavior
- tests claimed as passed when no tests were collected
- broad repo scans and high token burn
- Kimchi drifting outside the bounded stage scope
- ChatGPT/manual review relying on summaries instead of actual source files

This policy is enforced by:

```text
review_contracts/<stage>.contract.json
scripts/review_guardrails/stage_contract.schema.json
scripts/review_guardrails/stage_packager.py
scripts/review_guardrails/review_export_validator.py
scripts/review_guardrails/stage_completion_validator.py
docs/folder_structure.md
```

The scripts are not a replacement for manual review. They are mechanical guardrails that make the review package complete, bounded, and reviewable.

---

## 2. Core Principle

Every stage must be contract-driven.

Do not tell Kimchi:

```text
Implement SPR-02.
```

Instead, provide a full-stage micro-task contract:

```text
Read review_contracts/SPR-02.contract.json.
Execute the task_sequence in order.
Use only allowed files per task.
Run validators.
Run packager.
Create the review zip.
Stop if validators report a hard failure.
```

The contract tells Kimchi:

- exact task sequence
- allowed files to read
- allowed files to edit
- required source files
- required evidence logs
- required screenshots
- validators that define mechanical proof
- repair instructions if a task fails
- cost-control rules for follow-up work

---

## 3. Required Files in Every Review Export

Every review zip must include, at minimum:

```text
docs/folder_structure.md
docs/review_export_policy.md
scripts/review_guardrails/stage_contract.schema.json
scripts/review_guardrails/stage_packager.py
scripts/review_guardrails/review_export_validator.py
scripts/review_guardrails/stage_completion_validator.py
review_contracts/<stage>.contract.json
tests/results/evidence/validator_outputs/<stage>_packager_report.json
tests/results/evidence/validator_outputs/<stage>_review_export_validation.json
tests/results/evidence/validator_outputs/<stage>_stage_completion_validation.json
tests/results/evidence/logs/<stage>-zip-listing.log
```

Stage-specific zips must also include:

- all changed source/config/test files
- all relevant unchanged source/config/test files needed to review the claimed behavior
- all migration files involved in schema changes
- all focused tests or validation scripts created/updated
- all raw command logs used as evidence
- all screenshots used as frontend evidence
- file-read ledger
- evidence manifest
- closure summary
- current handoff file

If a required file exists in the repo but is missing from the review export, the packager must copy it into the export.

If a required file does not exist in the repo, the stage must fail until the file is created, restored, or the contract is corrected with an explicit reason.

---

## 4. Required Zip Structure

Review zips must preserve exact repo-relative paths.

Correct:

```text
services/restaurant-svc/app/api/v1/restaurants.py
services/user-svc/app/core/dependencies.py
apps/web/src/app/restaurants/[id]/page.tsx
apps/web/src/components/layout/MobileBottomNav.tsx
tests/results/evidence/logs/spr02-menu-endpoint.log
tests/results/frontend/customer/screenshots/restaurant-detail.png
review_contracts/SPR-02-v3.contract.json
```

Wrong:

```text
changed/restaurants.py
changed/main.py
reference/page.tsx
reference/restaurant.py
evidence/screenshots/homepage.png
```

Rationale:

- basename-only paths are ambiguous
- multiple files can share names like `main.py`, `restaurant.py`, `page.tsx`
- reviewers must be able to map every file back to its actual repo location
- source-grounded review is impossible with flattened paths

---

## 5. Forbidden Zip Contents

Review zips must not include:

```text
__MACOSX
.DS_Store
node_modules
.venv
.next
dist
build
__pycache__
*.pyc
old review zips
database files
runtime cache files
.env
.env.*
*.pem
*.key
*.p12
*.pfx
private keys
secrets
```

If a runtime config is needed for evidence, include a sanitized example file or a redacted evidence note. Do not package secrets.

---

## 6. Stage Contract Rules

The stage contract is the source of truth for a bounded stage.

Location:

```text
review_contracts/<stage>.contract.json
```

It must conform to:

```text
scripts/review_guardrails/stage_contract.schema.json
```

The contract must define:

- `stage`
- `cost_control`
- `local_first_policy`
- `repository`
- `review_export`
- `ownership`
- `task_sequence`
- `status_rules`
- `kimchi_updates`

Every task must include:

```text
task_id
scope_id
title
objective
sequence
task_type
allowed_files
validators
acceptance
repair_instruction
```

Every task should be small enough that Kimchi can implement it without reading broad repo context.

---

## 7. Kimchi-Owned vs Validator-Owned Fields

Kimchi may update only controlled execution fields:

```text
kimchi_updates.changed_files
kimchi_updates.files_read_end_to_end
kimchi_updates.commands_run
kimchi_updates.evidence_created
kimchi_updates.screenshots_created
kimchi_updates.known_blockers
kimchi_updates.requested_extra_files
kimchi_updates.notes
```

Kimchi must not manually set:

```text
validator_results.overall_status
validator_results.review_export_status
validator_results.stage_completion_status
validator_results.failed_validators
validator_results.next_action
```

Those fields are validator-owned.

If Kimchi needs to read/edit a file outside a task’s allowed file list, it must add it to:

```text
kimchi_updates.requested_extra_files
```

and stop unless the prompt explicitly permits automatic expansion.

---

## 8. Packager Rules

The packager is the deterministic export builder.

Script:

```text
scripts/review_guardrails/stage_packager.py
```

Required behavior:

- read the stage contract
- collect files from the contract
- copy missing-but-existing required files into the review export
- preserve repo-relative paths
- fail if a required repo file is missing
- fail/skip forbidden paths
- write a packager report JSON
- write a zip listing log
- create the final review zip

The packager is allowed to copy files. It is not allowed to invent evidence or decide that a task is complete.

Typical command:

```bash
python scripts/review_guardrails/stage_packager.py \
  --contract review_contracts/<stage>.contract.json \
  --clean
```

Expected output:

```text
review_exports/<stage>_scope_review.zip
tests/results/evidence/validator_outputs/<stage>_packager_report.json
tests/results/evidence/logs/<stage>-zip-listing.log
```

If packager status is not `PASS`, do not proceed to manual review.

---

## 9. Review Export Validator Rules

The review export validator checks package integrity.

Script:

```text
scripts/review_guardrails/review_export_validator.py
```

It validates:

- zip exists
- zip is readable
- zip entries are repo-relative
- forbidden folders/files are absent
- required files are present
- required file categories are present
- file-read ledger claims match actual zip entries
- logs are present and non-empty
- screenshots are present and non-empty
- validator outputs are included
- zip-listing log exists
- secret-like files are absent

Typical command:

```bash
python scripts/review_guardrails/review_export_validator.py \
  --contract review_contracts/<stage>.contract.json
```

Expected output:

```text
tests/results/evidence/validator_outputs/<stage>_review_export_validation.json
```

If the report is `NO-GO`, Kimchi must follow the `next_action` block and fix only the packaging/evidence issue identified.

Do not broaden implementation work when the failure is packaging-only.

---

## 10. Stage Completion Validator Rules

The stage completion validator checks task-level mechanical proof.

Script:

```text
scripts/review_guardrails/stage_completion_validator.py
```

It validates by `task_id`:

- source files exist
- Python functions/classes/routes/imports exist
- TypeScript components/imports exist
- code regex exists or is absent
- migrations add required columns
- package scripts exist
- logs contain required status/patterns
- logs do not contain forbidden errors
- curl logs prove expected HTTP status codes
- command logs prove expected exit codes
- pytest collected tests
- screenshots exist and pass basic non-blank checks
- JSON paths match expected values
- forbidden paid/cloud/external code is absent
- changed files stay within allowed files
- required files are present in zip

Typical command:

```bash
python scripts/review_guardrails/stage_completion_validator.py \
  --contract review_contracts/<stage>.contract.json
```

Validate one task only:

```bash
python scripts/review_guardrails/stage_completion_validator.py \
  --contract review_contracts/<stage>.contract.json \
  --task SPR-02.T002
```

Expected output:

```text
tests/results/evidence/validator_outputs/<stage>_stage_completion_validation.json
```

If a task fails, the report must include:

```text
next_action.task_id
next_action.scope_id
next_action.allowed_files
next_action.instructions
cost_control_for_followup
kimchi_next_prompt
```

Kimchi must fix only the failed task unless the validator requests packaging repair.

---

## 11. Evidence Rules

Evidence must be raw and replayable enough for review.

Acceptable evidence examples:

```text
curl command output with HTTP status
pytest output showing tests collected and pass/fail
frontend route HTTP logs
backend health check logs
database row-count query output
migration command output
Playwright/browser screenshot files
zip listing log
validator output JSON
```

Unacceptable evidence examples:

```text
"Verified manually"
"Looks good"
"All tests passed" with no raw test output
"No tests collected" while claiming tests passed
screenshot showing skeleton/loading state while claiming loaded UI
Markdown summary without raw log/source file
final report text without zip artifact
```

Every PASS claim must be supported by:

- source file
- raw evidence
- validator result
- screenshot if frontend behavior is claimed
- test or explicit live validation if runtime behavior is claimed

---

## 12. Screenshot Rules

Frontend screenshots must show the claimed state.

A screenshot is not acceptable if:

- it shows only skeleton placeholders while claiming loaded data
- it shows loading state while claiming loaded page
- it shows an error message while claiming success
- it omits the feature being claimed
- it is blank, tiny, corrupt, or invalid

Minimum screenshot evidence for frontend pages usually includes:

```text
homepage
restaurant list
restaurant detail
login page
authenticated state
mobile state, if mobile UI is claimed
error/empty state, if claimed
```

Mechanical validators can only check existence, size, and basic file validity. Manual review must still inspect screenshot content.

---

## 13. File-Read Ledger Rules

Every stage must include a file-read ledger.

The ledger must list, for every required file:

```text
file path
exists: yes/no
read end-to-end: yes/no
changed: yes/no
included in zip: yes/no
exact path inside zip
reason for inclusion/exclusion
scope IDs supported
task IDs supported
```

Rules:

- If the ledger says a file is included, it must exist in the zip.
- If the ledger says a file was read end-to-end, it should be included in the zip for reviewer verification.
- If a file is missing from repo, mark it as missing and fail.
- If a file is excluded, provide a reason.
- If the file is generated and too large, include the generator plus an explicit exclusion reason.
- The ledger must not claim `PASS`; validators own mechanical status.

---

## 14. Local-First MVP Policy

Until PR.08 is complete:

```text
No paid services.
No cloud services.
No paid APIs.
No production external integrations.
No ongoing-cost infrastructure dependency.
```

Defaults before PR.08:

```text
Use local computing.
Use open-source/free tools.
Use local PostgreSQL/Redis/filesystem.
Use fake/mock adapters for external services.
Docker is optional.
OpenSearch is optional.
External integrations must degrade gracefully.
```

Examples:

```text
Payment: fake/local adapter before PR.09
SMS/email: fake notification adapter before PR.09
Push: local WebSocket before PR.09
Maps/geolocation: mock/static local logic before PR.09
Object storage/CDN: local filesystem before PR.09
AI/personalization: rule-based/local mock before PR.09
Tracking: static/mock timeline before PR.09
OpenSearch: optional; DB fallback required
Images: local deterministic images; no Unsplash/cloud dependency
```

Forbidden before PR.08 unless explicitly approved:

```text
Stripe live
Razorpay live
Twilio
SendGrid
AWS S3
Google Maps paid API
Unsplash API dependency
OpenSearch hard dependency
production SMS/email/payment providers
```

---

## 15. Status Rules

Allowed statuses:

```text
PASS
PARTIAL
NO-GO
NOT-RUN
NOT-APPLICABLE
DEFERRED
```

A task may be marked `PASS` only if:

- all required validators pass
- source files exist
- source files are included in zip
- raw evidence exists
- screenshots exist for frontend claims
- tests are collected/run if tests are claimed
- zip/ledger consistency passes
- no hard validator failures exist

A task must be `PARTIAL` if:

- some proof exists but not enough for PASS
- frontend screenshot exists but does not fully prove behavior
- tests could not run and live validation is used instead
- scope item is intentionally adapted under local-first policy
- defer is allowed and documented

A task must be `NO-GO` if:

- required repo file is missing
- required zip file is missing
- ledger contradicts zip contents
- source evidence is absent for a source-level claim
- screenshot contradicts frontend claim
- tests are claimed but not collected
- runtime behavior fails hard
- forbidden zip entries or secrets are present
- stage changes files outside allowed scope without approval

---

## 16. Deferral Rules

Deferral must be explicit.

A deferred item must include:

```text
scope_id
task_id
defer reason
target stage
whether user approval is required
why it does not block the current stage
```

Do not silently convert required scope into partial/deferred.

If current stage policy says deferred items block next stage by default, do not proceed until the user explicitly accepts the deferral.

---

## 17. Cost-Control Rules

Target:

```text
Correction run: < 1M input tokens
Full sprint run: < 2M input tokens
```

Kimchi must not use broad context by default.

Every fresh bounded run must follow:

```text
Do not use old chat context.
Do not read old transcripts.
Do not use subagents unless explicitly authorized.
Do not scan the broad repo.
Read only files allowed by the task contract.
Edit only files allowed by the task contract.
Stop if additional files are required and not already allowed.
Stop if estimated context exceeds the contract token threshold.
Output only concise final report fields.
```

The validator report’s `kimchi_next_prompt` should be used for follow-up corrections. That prompt includes:

- failed task ID
- allowed files
- cost-control limits
- exact repair instruction
- instruction to rerun only that task validator first

This prevents follow-up prompts from silently consuming broad context.

---

## 18. Required Run Metrics

Every Kimchi run should append metrics to:

```text
tests/results/evidence/cost_control/kimchi_run_metrics.jsonl
```

Recommended fields:

```json
{
  "stage_id": "SPR-02",
  "contract_id": "SPR-02-v3",
  "run_type": "correction",
  "input_tokens": 4500000,
  "output_tokens": 22000,
  "duration_minutes": 23,
  "tasks_attempted": 11,
  "tasks_passed": 7,
  "validator_failures": 4,
  "accepted": false,
  "primary_failure_type": "missing_files_in_zip"
}
```

Use these metrics to measure whether micro-task contracts and validators reduce cost and rework.

---

## 19. Standard Stage Workflow

### Step 1 — Create or update contract

```text
review_contracts/<stage>.contract.json
```

The contract must cover the full bounded stage scope as micro-tasks.

### Step 2 — Kimchi runs preflight

```bash
python scripts/review_guardrails/stage_completion_validator.py \
  --contract review_contracts/<stage>.contract.json \
  --task <first-preflight-task-if-defined>
```

or run full validator if preflight is embedded.

### Step 3 — Kimchi executes task sequence

Kimchi works task-by-task.

Rules:

```text
Do not edit outside allowed files.
Run validator after each task or task group.
If validator fails, fix only that failed task.
Do not proceed to unrelated tasks until the failed task passes or is explicitly deferred.
```

### Step 4 — Kimchi updates controlled JSON fields

Kimchi updates only `kimchi_updates`.

### Step 5 — Run packager

```bash
python scripts/review_guardrails/stage_packager.py \
  --contract review_contracts/<stage>.contract.json \
  --clean
```

### Step 6 — Run review export validator

```bash
python scripts/review_guardrails/review_export_validator.py \
  --contract review_contracts/<stage>.contract.json
```

### Step 7 — Run stage completion validator

```bash
python scripts/review_guardrails/stage_completion_validator.py \
  --contract review_contracts/<stage>.contract.json
```

### Step 8 — If validators fail

Follow the generated:

```text
next_action
kimchi_next_prompt
```

Do not broaden scope.

### Step 9 — If validators pass

Manual review begins.

Manual review must still read:

- changed source files
- relevant unchanged source files
- tests
- contract
- validator outputs
- raw logs
- screenshots
- zip listing
- file-read ledger

---

## 20. Manual Review Rules

Manual review cannot rely on:

```text
Kimchi final report
Markdown summary
validator status alone
screenshot existence alone
file-read ledger alone
```

Manual review must verify:

- source code actually implements the claimed behavior
- evidence logs actually prove the claimed runtime behavior
- screenshots visually match claims
- package includes the right source files
- status table is honest
- remaining blockers are correctly classified
- no broad/out-of-scope changes occurred
- no paid/cloud/external dependency was introduced before PR.08

If manual review finds a mismatch, the stage is `NO-GO` or `PARTIAL`, regardless of validator status.

---

## 21. Automatic NO-GO Conditions

The stage is automatic `NO-GO` if any of these occur:

```text
review zip missing
review zip unreadable
review zip has flattened changed/reference folders
review zip lacks required backend/frontend/source files
review zip lacks contract JSON
review zip lacks guardrail scripts
review zip lacks folder_structure.md
review zip lacks validator outputs
file-read ledger claims files that are not in zip
required repo file missing
required screenshot missing
screenshot contradicts claimed frontend behavior
test log says no tests collected while tests are claimed
forbidden secrets/build artifacts included
source files changed outside allowed task files without approval
Kimchi manually edits validator-owned results
```

---

## 22. What Kimchi Should Do When a Validator Fails

Kimchi should not reinterpret the failure.

Kimchi should:

1. Read the validator report.
2. Use `next_action`.
3. Use `kimchi_next_prompt`.
4. Read only allowed files.
5. Edit only allowed files.
6. Fix only the failed task or packaging issue.
7. Rerun the failing validator.
8. Rerun full validators only after the targeted validator passes.
9. Update `kimchi_updates`.
10. Rerun packager.
11. Report concise results.

Kimchi should not:

- start the next sprint
- refactor unrelated code
- scan the broad repo
- use subagents
- include old chat context
- claim PASS from narrative
- skip packaging because “files were read”
- manually change validator results

---

## 23. Minimal Final Report Format

Kimchi final reports should be short.

Required fields:

```text
1. Stage status: PASS / PARTIAL / NO-GO
2. Contract path
3. Review zip path
4. Packager report path
5. Review export validator report path
6. Stage completion validator report path
7. Tasks PASS/PARTIAL/NO-GO counts
8. Exact files changed
9. Remaining blockers
10. Next recommended action
11. Token/cost metrics
```

Do not include long narrative unless the validator requests it.

---

## 24. Reviewer Acceptance Rule

A stage can be accepted only when:

```text
review_export_validator = PASS
stage_completion_validator = PASS or accepted PARTIAL with explicit user-approved deferrals
manual source-grounded review = GO
```

If any of those fail:

```text
Do not proceed to next stage.
Use validator next_action or write a targeted correction prompt.
```

---

## 25. Policy Summary

The system should make Kimchi a bounded code worker, not a broad autonomous agent.

Target behavior:

```text
contract tells Kimchi what to do
Kimchi edits bounded files
packager copies required files
validators find mechanical gaps
validator next_action tells Kimchi exactly what to fix
manual review verifies source and evidence
```

This is the standard review-export control model for all future BhojanGo stages.
