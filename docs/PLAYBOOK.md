# Engineering playbook

Lessons that apply across Srini's products: BhojanGo, SaaradhiGo and ETicketsGo.
Each is one rule and the reason for it. Follow them unless a PR says why not.

## Rules

1. **Specs live in `docs/specs` before any prompt that depends on them.**
   Why: a prompt built against a spec that only exists in chat or a doc elsewhere gets guessed, and the guesses differ every time.

2. **"No behaviour change" means the API contract stays the same. Prove it with a before/after API comparison and a `pg_dump --schema-only` diff.**
   Why: "it's just a refactor" is a claim; two empty diffs are evidence.

3. **CI must never hide failures: no `|| true`, no `continue-on-error` on gates.**
   Why: a gate that can't fail is decoration, and the breakage surfaces later where it costs more.

4. **Run `alembic check` in CI so models and migrations can't drift.**
   Why: drift passes every unit test and then breaks the first real `alembic upgrade` or autogenerate.

5. **Pin Expo native packages to the versions the SDK supports, and keep one React copy across the monorepo.**
   Why: mismatched native modules or two Reacts build fine, then crash at runtime on a device.

6. **`make ci` passing locally is the merge gate; GitHub Actions is a bonus.**
   Why: a merge shouldn't wait on Actions minutes or a stuck runner, and `make ci` runs exactly the same checks.

7. **Every paid provider has a free local fake behind the same interface, so the whole product runs at zero cost.**
   Why: anyone can run and test the whole product on day one, with no account, card or secret. Real keys plug in later without code changes.

8. **Ask about budget before proposing infrastructure.**
   Why: a well-sized design nobody can afford is the wrong design; the budget sets the shape.

9. **Keep shell scripts and Dockerfiles LF via `.gitattributes`.**
   Why: Windows checkouts turn them CRLF, and a CRLF script mounted into a Linux container fails with "not found" or `$'\r'` errors.

10. **Service-to-service endpoints are HMAC-signed, never left open.**
    Why: "internal" stops meaning internal the moment a load balancer route or a misconfigured network exposes it.

11. **Queue consumers are idempotent: record each event id, skip repeats.**
    Why: SQS and SNS deliver at least once, so without a record of handled events a retry sends the customer the same message twice.

12. **Every endpoint gets an access test: no token, wrong role, someone else's resource. A route without a policy fails CI.**
    Why: BhojanGo's first sweep found seven holes that unit tests had never asked about, including other customers' payments and other cities' menus.

13. **Authorise by permission and scope, never by role name.**
    Why: every hole the sweep found was a `role == "admin"` check, which let any admin act in any city, including read-only viewers.

14. **The release gate runs the real flow over HTTP on a throwaway stack, with no mocks and no admin help.**
    Why: BhojanGo's G1 found that no bag with options could reach checkout, which every mocked test had missed.

15. **Numbers shown to people come from the engine that charges them, never typed by hand.**
    Why: the hand-typed home-page bill drifted from the real rules, and the "delivery fee to RIDER" tag was wrong everywhere.

16. **Every city keeps its own time zone; the country's zone is only a label.**
    Why: Boise was running on New York time, so "today", payout weeks and greetings were all wrong there.

17. **Admin screens show settings in plain words; a test fails the build on raw JSON, "null" or "undefined".**
    Why: rule parameters leaked onto the page as JSON, which no operator can check at a glance.

18. **Every wait on an emulator, server or test run has a time limit and reports what it saw when it gives up.**
    Why: a hung tablet emulator answered `adb devices` but never finished booting; an unbounded wait sat for five hours. Cold-boot (`-no-snapshot-load`) and close the keyboard after each Maestro text entry on the tablet.

19. **End-to-end flows clean up after earlier runs before they start, not half-way through.**
    Why: an aborted run left orders in "ready"; dispatch offered one to the test rider, who then stayed busy with it, and the next run failed before its cleanup step. The rider flow now cancels its customer's leftovers before the app launches.

20. **Don't run emulator flows while `make ci` loads the machine; if one fails at its first screen, look at the screenshot before changing the flow.**
    Why: under CI load the tablet showed "System UI isn't responding" over the app and the sign-in assertion failed. Nothing was wrong with the app. The e2e runner now answers those dialogs, and the flows run after CI.

21. **Tests never delete shared fixtures they didn't create; and export `COMPOSE_PROJECT_NAME=bhojango-e2e` in every command that runs an e2e script.**
    Why: a regression test removed the conftest's "open all day" hours and every later integration test failed with "Closed now" after midnight in India; an admin e2e run without the variable joined the wrong compose network and couldn't find core-api.

22. **The emulator's System UI can hang for good; the e2e runner restarts it (adb root + pkill) and puts the port reversals back.**
    Why: on a software-rendered emulator "System UI isn't responding" stayed over the app after a fresh boot, so the first assertion of every flow failed; pressing back didn't clear it.

23. **Healthchecks prove the service answers the way clients connect (Postgres: `pg_isready -h 127.0.0.1`).**
    Why: during first start the Postgres image runs a socket-only server; a socket healthcheck said healthy and CI's migrations got "connection refused".

24. **Scripts are committed executable (`git update-index --chmod=+x`); Windows hides a missing bit that Linux won't.**
    Why: LocalStack skipped a 100644 init hook on GitHub's Linux runners, so no queues existed and G1 failed there for weeks while passing locally.

25. **A test that walks routes must prove it found some.**
    Why: FastAPI now wraps included routers (`_IncludedRouter`); a contract test that only looked for `APIRoute` found nothing and would have passed while checking nothing.

26. **Money formatting never rounds: "no decimals" means drop ".00" from whole amounts only.**
    Why: menus written for whole rupees showed a $14.50 bowl as "$15" in the US.

27. **Metrics and the console come from one function.**
    Why: the KPI gauges reuse the admin overview's `_totals`, so Grafana and the console can't disagree, which was the bug A5 fixed.

28. **Time-box side quests; report what's missing.**
    Why: Grafana screenshots would not render in the headless container after three attempts, while the monitoring itself was verified through its APIs. We moved on and said so.

29. **A load test runs each path on its own before the mix.**
    Why: with everything at once, core_api looked slow (quote p95 21 s) when realtime was the cause. Alone, core_api was under 112 ms; realtime's exhausted Redis pool and a burst of trackers calling core_api were the problem.

30. **Long-lived connections share resources per process, never one each.**
    Why: one Redis pub/sub connection per WebSocket ran out at 200 watchers and took every other Redis call down with it.

31. **Run every scanner again after the fixes, and keep a written reason for each finding you accept.**
    Why: the first trivy pass showed fixable CVEs inside npm, which ships in the Node base image but isn't used at runtime. After removing npm and moving to Debian 13, only unfixed base packages were left, and the report records why each accepted item stays.

32. **Images run as a non-root user; local volumes from older images get a one-shot chown step, not a root container.**
    Why: switching core-api to uid 10001 would have broken everyone's existing JWT-key volume. `keys-init` hands it over once.

33. **A backup counts only after it has been restored onto a wiped disk and the app passes its end-to-end test on it.**
    Why: a dump file proves nothing. The drill deletes the volume, restores, checks every table's row count and runs G1 on the result, in two minutes, so it can run every quarter.

34. **Prove a scanner can fail before trusting a clean result: plant a fake finding and check it's caught.**
    Why: gitleaks reported "0 leaks" for weeks because our config's empty `[extend]` turned its default rules off; with them on, history had 55 findings (all dead tokens). The pre-commit hook and `make ci-secrets` now run a self-test first.

35. **Before a new host, run the app locally the way that host will run it, and make it part of CI.**
    Why: Railway has no SNS/SQS and no PostGIS. Reading its docs didn't show that our event flow depended on SNS; a compose overlay shaped like Railway (`make ci-railway`) did, and it now keeps the Redis Streams path tested. Also check the host's current config format: Railway stops reading `railway.toml` on 2026-12-01.

36. **Before a pilot, run a long, mixed rehearsal with bots doing what people do, and measure fairness and alert noise, not only speed.**
    Why: the 5-minute k6 test passed with p95 under 100 ms, but two hours of a dinner rush showed orders waiting 52 minutes while newer ones got riders (dispatch wasn't oldest-first), connections dropped at uvicorn's 5 s keep-alive, and a payment alert that would page on every busy evening.

37. **Report status against each task's "done when", not against the code.**
    Why: mapping the 44 tracker tasks, several features were finished in code but their task still couldn't be shown done (payments "live in test mode", web pages "indexed", alerts "reach on-call phone"). Calling them done would have hidden what's waiting on accounts and money.

## How to add a lesson

Whenever a bug, stall or surprise costs more than an hour, add a rule here in the same PR as the fix.

- One short rule in bold, then one line of "Why:". Name the tool or command if there is one.
- Make it general enough to apply to all three products. Facts about one product belong in that product's README.
- If a new rule replaces an old one, edit the old one instead of adding another.
- Keep this file under two pages: merge or cut rules before it grows past that.
