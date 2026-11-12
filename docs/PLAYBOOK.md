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

## How to add a lesson

Whenever a bug, stall or surprise costs more than an hour, add a rule here in the same PR as the fix.

- One short rule in bold, then one line of "Why:". Name the tool or command if there is one.
- Make it general enough to apply to all three products. Facts about one product belong in that product's README.
- If a new rule replaces an old one, edit the old one instead of adding another.
- Keep this file under two pages: merge or cut rules before it grows past that.
