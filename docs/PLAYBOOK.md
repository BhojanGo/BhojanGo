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

34. **Prove every scanner works by planting a fake finding in a test; a scan with no findings proves nothing until it has caught one.**
    Why: gitleaks reported "0 leaks" for weeks because our config's empty `[extend]` turned its default rules off; with them on, history had 55 findings (all dead tokens). Canaries now run in `make ci` for gitleaks (a JWT and an AWS key, built at run time), semgrep (`pickle.loads`, `shell=True`) and the access-control sweep (an unpoliced route, an open route, a missing ownership check); turning the gitleaks defaults off again fails the build.

35. **Before a new host, run the app locally the way that host will run it, and make it part of CI.**
    Why: Railway has no SNS/SQS and no PostGIS. Reading its docs didn't show that our event flow depended on SNS; a compose overlay shaped like Railway (`make ci-railway`) did, and it now keeps the Redis Streams path tested. Also check the host's current config format: Railway stops reading `railway.toml` on 2026-12-01.

36. **Before a pilot, run a long, mixed rehearsal with bots doing what people do, and measure fairness and alert noise, not only speed.**
    Why: the 5-minute k6 test passed with p95 under 100 ms, but two hours of a dinner rush showed orders waiting 52 minutes while newer ones got riders (dispatch wasn't oldest-first), connections dropped at uvicorn's 5 s keep-alive, and a payment alert that would page on every busy evening.

37. **Report status against each task's "done when", not against the code.**
    Why: mapping the 44 tracker tasks, several features were finished in code but their task still couldn't be shown done (payments "live in test mode", web pages "indexed", alerts "reach on-call phone"). Calling them done would have hidden what's waiting on accounts and money.

38. **When porting code, have the original produce reference outputs and require the port to match them exactly.**
    Why: the batch engine's ported unit tests check shapes ("score > 0", "pickup before delivery"); a parity fixture made by the TypeScript engine itself (18 scorings, 3 cycles) pins exact scores, distances and routes, including JavaScript's rounding, which Python's `round()` does differently.

39. **When a test turns a feature on, measure that it did something before comparing results.**
    Why: the first batching-on soak section looked like a clean comparison (delivery times, pay, errors), but it had offered 0 batches: the pairing window was 20 seconds, so two orders from one kitchen never overlapped. Counting batch offers caught it; the fix (#54) put cooking orders in the pool.

40. **A status label must be true of the version it's on: "Live" only for the one running now.**
    Why: rule history showed every published version as "Live", including ones replaced months ago, so an admin couldn't tell which commission was charging. Now an older version says "Replaced on <date>" or "Ended on <date>".

41. **Report the runs on the main branch, not only the PR checks.**
    Why: every PR check was green while the pipeline on `dev` failed 18 times (G1 on GitHub for 15 merges, a flaky order-code search, a Docker Hub outage). Reports now include the run link and per-job test counts for each merge commit (`tools/ci/evidence.sh`).

42. **"Platform revenue" isn't what the platform keeps. Take payment fees off before calling an order profitable.**
    Why: a Boise card order showed $4.60 platform revenue, but Stripe took $1.47 of the charge. Each order's split now records its payment fee (the rule version is in `rules_used`), and Finance shows contribution per order after fees, rider pay, the offers we fund and refunds. Orders from before the rule exist are estimated from today's rule, and the page says how many.

43. **Pay for the work the rider actually does: a batch's second drop-off isn't a second trip.**
    Why: batching paid every order its full base, so a two-order batch cost the platform almost what two separate trips did. That undid most of the saving, and the rider earned two bases for one pickup. Now later drop-offs pay distance + waiting + a city batch bonus. The bonus is recorded on the order when the rider accepts, so a later rule change doesn't move pay already earned. The offer card shows the batch rate before the rider accepts.

44. **Before a simulation uses one of our words, check what it means in our product.**
    Why: the soak's first try paid 15% of Boise orders by "wallet", meaning Apple Pay. In BhojanGo, "wallet" is the customer's own balance, so the orders were refused for an insufficient balance. Hyderabad's soak also assumed Boise's layout, with every kitchen reaching every home and no dish needing a choice. Both runs were stopped and rerun, not reported.

45. **Before setting a spending limit, find out what it covers.**
    Why: the brief asked for a $20 hard limit on QA. Railway's limits belong to the whole workspace, not a project, and a hard limit takes *every* workload offline. Our workspace runs other live projects that already spend about $23 a month, so a $20 cap would have stopped them mid-month. QA got per-service CPU and memory caps and sleeping frontends instead; the workspace limit stays the user's decision.

46. **`--host ::` doesn't mean "every address".**
    Why: asyncio sets `IPV6_V6ONLY` on a socket bound to `::`, so uvicorn listened on IPv6 only. Railway's health check and edge connect over IPv4 and every QA backend failed its health check, with no request in the access log. Bind to what the platform's health check uses (`0.0.0.0` on Railway), and check for the probe's request in the access log before blaming the app.

47. **Seal a secret only after you know how the tests will reach what it protects.**
    Why: a sealed Railway variable can't be read back by anyone, and project tokens can't `railway ssh`. With Postgres and Redis kept private, nothing on a workstation could reach the QA database. Seeding, migration checks, G1 and the integration suite ran in a temporary service inside the environment (`qa-runner`), which gets the secrets through Railway references and never prints them.

48. **Translate a platform's names at the boundary.**
    Why: Railway's bucket credentials say `urlStyle: virtual-host`; boto3 only knows `virtual`, `path` or `auto`. Passing it through either crashes or quietly falls back to path-style, which Railway's new buckets don't serve. `S3_ADDRESSING_STYLE` is now normalized when settings load, with a test.

49. **"Applied" isn't proof; a clean plan is.**
    Why: `railway config apply` reported the bucket as applied, but it existed only at project level. The next plan still wanted to create it, and the QA environment had no bucket until an environment patch deployed it. A volume left without a region also made the next plan propose a destructive change. After every apply, plan again until it says nothing.

50. **A config helper called "random" may not be random.**
    Why: the Railway IaC SDK's `ctx.randomString()` is a SHA-256 of the environment name and a label, so anyone with the repo can recompute it. QA's secrets were generated locally and stored sealed through the API; nothing secret is in `.railway/railway.ts`.

51. **On Windows, Python's `write_text` writes CRLF, and a shell script with CRLF fails in Linux.**
    Why: patch scripts rewrote shell scripts with `\r\n`, and the QA runner died with `set: Illegal option -`. `.gitattributes` keeps commits LF, but the runner was staged from the working tree. The staging step now strips carriage returns from `*.sh`. Shell scripts are now edited with tools that keep LF.

52. **A frontend that bakes in public URLs needs them before its first build, and a health check needs a page that answers 200 without signing in.**
    Why: web's first QA build failed on `new URL("https://")`, because its own domain didn't exist yet. Admin's health check failed on `/`, which redirects to sign-in (307). Domains are now created right after the first apply, and admin's health check is `/login`. Tests that assumed the production site URL (`https://bhojango.com` in canonical links and the sitemap) now read it from the environment.
53. **Behind a proxy, a rate limit keyed on "the client's address" is keyed on the proxy.**
    Why: on Railway QA, core_api logged every request as coming from Railway's proxies (`100.64.x.x`). The sign-in limit (10 a minute) and the OTP limit (3 a minute) were shared by every user behind each proxy node. The partner app's Maestro sign-ins started failing with nobody else using QA, and real users would have locked each other out at launch. Trusting `X-Forwarded-For` didn't help: it ends in Railway edge hops. The client is in `X-Real-IP`, which Railway's edge sets and a client can't override, so the limiter and the request log now read the header named in `CLIENT_IP_HEADER`.

54. **Infrastructure as code removes what it doesn't know about.**
    Why: a temporary `qa-runner` service, created outside `.railway/railway.ts`, showed up in the next plan as "Delete service qa-runner". Applying a one-line variable change would have deleted the runner mid-test. Read every delete line in a plan; for a quick change while a temporary service exists, set the variable directly and apply after the service is gone.

## How to add a lesson

Whenever a bug, stall or surprise costs more than an hour, add a rule here in the same PR as the fix.

- One short rule in bold, then one line of "Why:". Name the tool or command if there is one.
- Make it general enough to apply to all three products. Facts about one product belong in that product's README.
- If a new rule replaces an old one, edit the old one instead of adding another.
- Keep this file under two pages: merge or cut rules before it grows past that.
