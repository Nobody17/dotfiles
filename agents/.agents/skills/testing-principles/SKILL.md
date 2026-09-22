---
name: testing-principles
description: Design, write, review, or repair tests across frameworks. Use for coverage decisions, test doubles, brittle assertions, and flaky suites. Excludes production-only changes and test-runner setup without test-design work.
---

# Testing principles

## Workflow

1. Read nearby tests and the project's test commands. Identify the observable contract and the regression or failure the test must detect.
2. Map changed behavior to cases: normal use, meaningful boundaries, and relevant failures. Account for each distinct rule or risk with an existing test, a new test, or an explicit coverage gap. Choose cases by consequence and behavior, not by a test-count quota.
3. Choose the narrowest test level that can detect the failure. Pure logic needs real values; persistence semantics need a real test database; browser behavior needs a browser. Keep integration coverage where isolated tests cannot prove collaborators work together.
4. For a bug, reproduce the failure before fixing it when feasible. Verify that the test fails because of the bug, not broken setup. If the fix already exists, safely check the test against the old behavior when practical; otherwise report that regression sensitivity is unverified. For a requested test-first workflow, use the `tdd` skill.
5. Write or revise tests using the rules below. In a review-only task, identify the missing assertion or scenario without changing files.
6. Run the focused tests, then the affected suite and required project checks. Completion means the selected cases are covered and checks pass, or the report names the exact command, blocker, and remaining gap. A skipped test is a gap, not a pass.

For Ruby tests, also read [ruby-testing](../ruby-testing/SKILL.md) for language and framework guidance.

## Contracts and assertions

Assert results visible to a caller: returned values, persisted state, errors, rendered output, or a required message to another system. Keep expectations independent of the implementation's calculation; copying its algorithm into the test can preserve the same defect on both sides.

Use assertions that would reject a plausible wrong result. A success status alone does not prove the response body or stored state is correct. For rejected operations, assert both the reported failure and any required absence of side effects.

Interaction assertions are useful when the interaction is the contract, such as sending the correct payment request once. Assert contract-relevant arguments and ordering; local helper calls usually are not that contract. Check a double's assumed interface against a real adapter or a separate contract test where drift is a risk.

Use exact text, snapshots, or ordering when they are part of the contract. Otherwise assert stable semantic properties. Keep snapshots small enough to review and inspect changes before accepting them.

## Test doubles and real dependencies

Prefer real inputs and collaborators when execution is fast, controlled, and isolated. Use scoped doubles for remote services, expensive operations, and hard-to-produce failures. Choose temporary files or a disposable database when filesystem or database semantics are under test.

Control time and randomness when they influence the expected result. Prefer an existing injection seam or the framework's scoped helper. Widespread patching of local methods suggests a poor test boundary; consider a smaller seam before proposing a production redesign.

## Structure and isolation

Name a test after its condition and expected outcome. Follow project file conventions and keep setup near the assertions it explains. Extract helpers for repeated domain actions while keeping scenario inputs and expectations visible.

Arrange, act, and assert should be easy to distinguish. One test should tell one behavioral story; that story may need several actions and assertions, such as signing in and completing checkout. Split unrelated outcomes, not every use of “and.”

Give each test its own mutable state. Restore global configuration and release resources even when assertions fail. Isolate database records, files, queues, and caches between tests and parallel workers. Shared setup should contain immutable data or explicitly reset resources.

Wait for asynchronous work to finish and surface its errors. Use bounded, retrying assertions or completion signals for eventual state; use controlled clocks for timer-driven logic. Fixed sleeps make correctness depend on machine speed.

## Repairing failures

Reproduce a failure with its seed, test order, worker count, and relevant environment. Compare isolated and suite runs when shared state is suspected. Repeated passing runs alone do not explain a flaky failure.

Treat a failure during refactoring as evidence to investigate. Establish whether the public contract changed before editing expectations. Fix regressions in production code; revise implementation-coupled tests once unchanged behavior is established. For an intentional contract change, update the expectation and check affected consumers.

Serial execution, longer timeouts, and retries can help diagnose failures. A lasting repair must explain and address the shared resource, missing synchronization, or environmental assumption that caused them.
