#!/bin/sh
# Evidence for a report: the GitHub runs on dev for a merge commit, each job's
# result and link, and the test counts each job printed (pytest passed/skipped,
# Playwright N/N, make ci lines).
#   tools/ci/evidence.sh <sha> [timeout-seconds]      # waits for the runs to finish (default 1800 s)
# Prints Markdown. Exits 1 if any job on dev failed.
set -u
SHA="$(git rev-parse "$1" 2>/dev/null || echo "$1")"  # gh needs the full SHA
WAIT="${2:-1800}"
REPO="BhojanGo/BhojanGo"
end=$(( $(date +%s) + WAIT ))
while :; do
  runs=$(gh run list --repo "$REPO" --branch dev --commit "$SHA" --json databaseId,workflowName,status,conclusion,url \
         --jq '.[] | "\(.databaseId)\t\(.workflowName)\t\(.status)\t\(.conclusion)\t\(.url)"' 2>/dev/null)
  [ -n "$runs" ] && ! echo "$runs" | awk -F'\t' '$3 != "completed"' | grep -q . && break
  [ "$(date +%s)" -ge "$end" ] && { echo "runs for $SHA not finished after ${WAIT}s:"; echo "$runs"; break; }
  sleep 30
done
red=0
echo "$runs" | while IFS="$(printf '\t')" read -r id wf st concl url; do
  [ -z "$id" ] && continue
  echo "- **$wf** on dev @ \`$(echo "$SHA" | cut -c1-7)\`: **$concl** ($url)"
  gh run view "$id" --repo "$REPO" --json jobs --jq '.jobs[] | "\(.databaseId)\t\(.name)\t\(.conclusion)"' |
  while IFS="$(printf '\t')" read -r jid name jc; do
    counts=$(gh run view --repo "$REPO" --job "$jid" --log 2>/dev/null |
      grep -oE "[0-9]+ passed(, [0-9]+ (skipped|failed|deselected|xfailed))*|[0-9]+ failed, [0-9]+ passed|[0-9]+/[0-9]+ passed" |
      sort | uniq -c | awk '{c=$1; $1=""; print substr($0,2) (c>1?" (x"c")":"")}' | paste -sd ';' - | sed 's/;/; /g')
    echo "  - $name: $jc${counts:+ · $counts}"
  done
  [ "$concl" = "success" ] || red=1
done
gh run list --repo "$REPO" --branch dev --commit "$SHA" --json conclusion --jq '.[].conclusion' | grep -qv success && exit 1
exit 0
