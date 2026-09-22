# Rails testing

Source: [Testing Rails Applications](https://guides.rubyonrails.org/testing.html), consulted 2026-09-17. Check the application's Rails version before using helpers.

- Use model tests for domain logic, request/integration tests for HTTP behavior, and system tests for browser-dependent flows. Inspect response content and state changes, not just status.
- Prefer Rails assertions such as `assert_difference` for record changes and `assert_no_difference` for rejected writes. Reload records when checking persisted results.
- Keep transactional cleanup by default. Tests involving concurrent transactions may need `use_transactional_tests = false`; scope this change and provide explicit cleanup. See [transactions](https://guides.rubyonrails.org/testing.html#transactions).
- Distinguish enqueueing from execution. `assert_enqueued_with` checks scheduling; `perform_enqueued_jobs` exercises execution. Calling a job's `perform` directly bypasses framework behavior. Test mail content separately from delivery scheduling. See [jobs](https://guides.rubyonrails.org/testing.html#testing-jobs) and [mailers](https://guides.rubyonrails.org/testing.html#testing-mailers).
- Use block-scoped `travel_to` for time-dependent behavior and Capybara assertions for browser state.
- Rails creates per-process test databases for parallel runs; isolate other shared resources yourself.
- `bin/rails test` excludes system tests. Run `bin/rails test:system` when relevant, or `bin/rails test:all` for both. Follow project commands for RSpec suites.
