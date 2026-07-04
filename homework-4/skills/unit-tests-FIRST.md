---
name: unit-tests-FIRST
description: FIRST principles for writing unit tests (Fast, Independent, Repeatable, Self-validating, Timely). Used by the Unit Test Generator agent as the acceptance bar for every test it writes.
---

# FIRST Principles for Unit Tests

Every test the Unit Test Generator writes must satisfy all five properties below. A test that
violates any one of them is not acceptable output, even if it happens to pass.

## F — Fast

- No real network calls, real sleeps/timers, or unnecessary I/O. Mock or fake anything slow.
- A single test should run in well under a second. If a test needs a real subprocess or
  filesystem write (e.g. this project's CLI tests), keep the scope to exactly what's under
  test and avoid redundant setup work per test.
- A slow test suite gets skipped by developers under deadline pressure — speed is not a nice
  -to-have, it's what keeps the suite actually run.

## I — Independent

- Each test must be runnable alone, in any order, with no dependency on another test having
  run first (no shared mutable state, no relying on a previous test's side effects).
- Use isolated fixtures (temp directories, fresh env vars, fresh fixture instances) rather
  than a shared global vault/database/file that tests take turns mutating.
- Failure of one test must never cascade into unrelated tests failing.

## R — Repeatable

- The same test run against the same code must produce the same result every time, in any
  environment (dev laptop, CI, different machine) and in any order.
- No dependence on system time, random values without a fixed seed, external services, or
  ambient environment state that isn't explicitly set up by the test itself.
- If the code under test needs an environment variable or key, the test sets it itself rather
  than assuming it's already present in the shell.

## S — Self-validating

- The test produces a clear boolean pass/fail via assertions — no tests that require a human
  to read printed output and judge correctness.
- One logical behavior per test, with assertion(s) that directly check that behavior. Avoid
  bundling multiple unrelated behaviors into one test where a failure wouldn't clearly say
  which one broke.
- Failure messages should make the discrepancy obvious without needing to re-run in a
  debugger (e.g. assert on the specific field/value, not just "result is truthy").

## T — Timely

- Tests are written for the code as it exists *now*, immediately after the change that
  introduced or altered the behavior — not deferred to "later."
- Cover the specific bug/change just made: the previously-broken path plus the boundary
  conditions right next to it (e.g. empty result, single match, multiple matches for a search
  fix). Do not attempt to backfill unrelated legacy coverage — that's out of scope for a
  change-scoped test generation pass.

## Applying FIRST when writing a test

For every test written, check off all five before including it:

- [ ] Fast — no unnecessary sleeps/network/heavy setup
- [ ] Independent — isolated fixtures, no shared state, runs in any order
- [ ] Repeatable — no reliance on time/randomness/ambient env state
- [ ] Self-validating — clear assertions, one behavior per test
- [ ] Timely — targets the actual change just made, not unrelated legacy code

If a test can't satisfy one of these without major rework, say so explicitly in the test
report rather than shipping a test that silently violates FIRST.
