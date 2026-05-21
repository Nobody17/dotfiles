---
name: testing-principles
description: Use when writing, adding, reviewing, or refactoring tests; deciding what behavior and edge cases to test; choosing mocks vs real implementations; improving flaky or brittle test suites; planning bug-regression or feature test coverage; or evaluating test quality. Do not use for production-only implementation/refactoring or test-runner configuration unless test design or quality is requested. Applies regardless of framework.
---

# Testing Principles

Framework-agnostic principles for writing tests that are fast, reliable, and resilient to refactoring. These apply whether using vitest, Jest, Mocha, or any other test runner.

## Workflow

When asked to write, review, or repair tests:

1. Identify the observable behavior and public API being tested.
2. For bugs or new features, define the failing regression/behavior test before changing source code. If the task is review-only, state the test that should fail before the fix.
3. Choose the test level deliberately: pure unit test, integration test with real collaborators, or end-to-end workflow. Use the lowest level that still proves the behavior.
4. Use real inputs for pure logic. Mock only external boundaries that make the test slow, nondeterministic, or side-effectful.
5. Cover the happy path, edge cases, error paths, and boundary conditions. Do not treat “behavioral test” as permission for one minimal happy-path test.
6. Structure each test with Arrange, Act, Assert; keep setup isolated and deterministic.
7. Run the smallest relevant test command. If you cannot run it, say exactly what remains unvalidated.

## Gotchas

- Do not apply this skill to production-only implementation/refactoring or test-runner configuration unless the user asks about test behavior, coverage quality, flakiness, or mock strategy.
- “Behavioral” means assert observable outcomes, not internals. It does not mean “test less.”
- Databases are external boundaries for unit tests, but use a disposable real database when the behavior under test is persistence, migrations, transactions, constraints, or query semantics.
- If refactoring breaks a test while external behavior is unchanged, rewrite the test around behavior instead of updating it to match new internals.
- Do not assert detailed mock call shapes for your own code when an observable outcome can be asserted instead.
- If a test needs many monkey-patches or mocks of local code, call out the coupling and prefer a dependency-injection seam or pure-core/imperative-shell split.
- Never add sleeps to fix async or flaky tests. Use fake timers, polling assertions, or event-driven signals.

## What Makes a Good Test

A good test has three properties:

1. **Deterministic** — same result every time. No flakiness from timing, ordering, or external state.
2. **Behavioral** — tests what the code does, not how it does it. Refactoring internals should never break a test.
3. **Isolated** — one test failing doesn't cause others to fail. Tests can run in any order.

## Arrange-Act-Assert (AAA)

Every test follows this structure:

```
// Arrange -- create the world the test needs
const db = await createTestDatabase()
const service = new UserService(db)

// Act -- do the one thing being tested
const result = await service.createUser({ name: 'Alice' })

// Assert -- verify the outcome
expect(result.name).toBe('Alice')
expect(result.id).toBeDefined()
```

Separate the three phases with blank lines — no `// Arrange` / `// Act` / `// Assert` comments needed. If you need more than one "Act" step, the test is testing too much. Split it.

## Write Failing Tests First

When fixing a bug, write a failing test that reproduces it **before** touching the source code. The test proves you understand the bug and guards against regression. Once the test fails for the right reason, fix the code. The test stays.

This also applies to new features: write the test first to clarify the expected behavior before implementing.

## What to Mock

### Mock external boundaries
- Remote network requests and production external services
- Databases for unit tests; use disposable real databases for integration tests that verify persistence, migrations, transactions, constraints, or query semantics
- File system I/O when the filesystem behavior itself is not the subject of the test
- System clock (`Date.now()`, `setTimeout`)
- Random values (`Math.random()`, `crypto.randomUUID()`)
- Third-party services with side effects (email, payment)

### Don't mock
- Pure functions (just call them)
- Value objects / DTOs (just construct them)
- Your own code that has no side effects
- Language built-ins (unless there's a mocking utility for it, like timers)
- Types and interfaces (they don't exist at runtime)

### The litmus test
If you can test something by passing real inputs and checking real outputs — do that. Mocking is for when you **can't** get deterministic, fast, or side-effect-free execution otherwise.

This principle guides **what kind** of test to write — behavioral tests with real inputs instead of mocking everything. It is not about test thoroughness. Real inputs don't excuse skipping edge cases, error paths, or boundary conditions. A function that takes a CSV and returns JSON should be tested with real CSV strings (not mocked internals), **and** it should be tested for empty input, malformed input, type mismatches, and edge cases. A single happy-path test with real inputs is not "following the litmus test" — it's insufficient coverage.

## Test Invariants, Not Internals

```typescript
// BAD: Testing implementation details
expect(service.users.length).toBe(1)
expect(service.lastQuery).toContain('INSERT INTO users')

// GOOD: Testing observable behavior
const user = await service.findUser(alice.id)
expect(user.name).toBe('Alice')
```

The BAD test breaks if you switch from an array to a Map, or change the SQL dialect. The GOOD test survives any internal change.

## Naming Tests

Name tests as if they're documentation. Use "it" + description of behavior:

```typescript
test('returns empty list when no users exist')  // BAD
test('returns an empty list when no users exist')  // GOOD
it('throws ValidationError when email is invalid')  // GOOD
```

The test name + describe block should form a readable sentence: "UserService > findAll > returns an empty list when no users exist".

Use `test` or `it` — both are equivalent. The choice is a project convention. Pick one and be consistent across the codebase.

## Structure Tests by Behavior

Group by the behavior being tested, not by method name:

```typescript
// BAD: Structure mirrors implementation
describe('createUser', () => { ... })
describe('deleteUser', () => { ... })

// GOOD: Structure mirrors capability
describe('user registration', () => { ... })
describe('account deletion', () => { ... })
```

This survives method renames and refactoring.

## Test One Thing Per Test

Each test verifies a single behavior. If a test has multiple assertions, they should all be about the same logical outcome:

```typescript
// OK: Multiple assertions, same behavior
it('creates user with correct defaults', () => {
  const user = createUser({ name: 'Alice' })
  expect(user.name).toBe('Alice')
  expect(user.role).toBe('member')
  expect(user.active).toBe(true)
})

// BAD: Testing two unrelated behaviors
it('creates user and sends email', () => {
  const user = createUser({ name: 'Alice' })
  expect(user.name).toBe('Alice')
  expect(emailService.sentEmails).toHaveLength(1)  // Separate concern
})
```

The BAD test couples user creation to email delivery. Split into two tests.

A practical heuristic: if a test name contains "and", it's testing two things — split it.

## File Organization

- **One test file per source module.** Tests for `user.service.ts` go in `user.service.test.ts` (or your project's convention).
- **Group related tests with `describe` blocks.** Keep nesting shallow — 1 to 2 levels max. Deeply nested blocks are hard to scan.
- **Split large test files.** If a test file grows beyond ~300 lines, it's covering too many behaviors. Split by feature area.

## Prefer Dependency Injection Over Monkey-Patching

```typescript
// BAD: Monkey-patching module internals
vi.spyOn(UserService.prototype, 'sendEmail').mockResolvedValue()

// GOOD: Inject the dependency
const emailService = { send: vi.fn().mockResolvedValue(undefined) }
const service = new UserService(emailService)
```

Injected dependencies make test setup explicit. Monkey-patching hides what's being mocked and couples tests to internal structure.

## Testing Async Code

- Always `await` or return the promise. Unawaited promises cause false positives.
- Use framework async matchers: `expect(promise).resolves.toBe(x)`, `expect(promise).rejects.toThrow()`
- Avoid arbitrary `setTimeout` waits — use polling (`expect.poll()` in vitest) or event-driven signals
- Test both resolution and rejection paths

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Tests knowing about private methods | Breaks on refactoring | Test through public API only |
| `mock.calls[0][2].foo` assertions | Tests argument shapes, not behavior | Assert observable outcomes |
| Tests that need `--runInBand` to pass | State leakage between tests | Isolate test state; use beforeEach cleanup |
| Mocking everything | Tests test mocks, not code | Only mock external boundaries |
| Snapshot testing mutable state | Snapshots vary by run (timestamps, IDs) | Mock time/random; or avoid snapshots for dynamic data |
| Giant beforeAll with shared mutable state | Tests depend on execution order | Each test sets up its own state |
| Testing error messages verbatim | Breaks on wording changes | Test error type and key properties |
| Rationalizing minimal tests as "behavioral" | "Skill says test with real inputs so a couple quick tests are fine" | The litmus test is about approach (real vs mocked), not thoroughness. Every external boundary needs edge case, error path, and happy path coverage regardless of mocking strategy. |

## Rationalization Table

When under pressure, common excuses for skipping testing principles:

| Excuse | Reality |
|--------|---------|
| "The litmus test says use real inputs — quick inline fixture tests follow that" | The litmus test guides test *approach*, not test *thoroughness*. Real inputs don't replace edge case coverage. |
| "It works, I manually tested it" | Manual testing is ephemeral. Automated tests persist and catch regressions. |
| "I'll write better tests tomorrow" | Tomorrow brings new pressures. The code is fresh now; tests written tomorrow will be worse. |
| "Testing is slowing me down" | Untested code slows down the entire team when it breaks in production. |
| "Tests after achieve the same purpose" | Tests-after describe what code does. Tests-first define what code should do. They catch different bugs. |
| "This is too simple to need thorough tests" | Simple code breaks in simple ways. Edge cases don't care about complexity. |

## When a Test Breaks During Refactoring

If a test fails and the external behavior hasn't changed, the test was coupled to implementation details. Update the test to verify behavior, not update it to match the new internals.

If a test fails and the external behavior HAS changed, that's either:
- A regression (fix the code)
- An intentional change (update the test + check for other consumers)

## Red Flags

- "I need to mock everything to test this" → function is too coupled. Refactor toward pure core + imperative shell.
- "I need to know the order tests run" → tests share state. Isolate.
- "This test passes locally but fails on CI" → timing or environment dependency. Use fake timers, explicit env.
- "I changed internal code and 10 tests broke" → tests are testing implementation. Rewrite toward behavioral assertions.
- "I need to add a sleep to make the test pass" → race condition. Use polling or event-driven assertions.
- "I'm following the skill — testing behavior with real inputs" while writing fewer tests than the situation demands → the litmus test is about approach, not thoroughness. Real inputs don't excuse skipping edge cases, error paths, or boundary conditions.
