---
name: ruby-testing
description: Write, review, or repair Ruby tests using the project's Minitest or RSpec conventions. Use for Ruby-specific test data, doubles, isolation, and Rails test-level or helper choices.
---

# Ruby testing

Read [testing-principles](../testing-principles/SKILL.md) for shared coverage, assertion, and validation rules unless already loaded. This skill adds Ruby-specific decisions.

## Establish the test environment

Read the Gemfile, lockfile, test helpers, nearby tests, and CI commands. Identify the Ruby and framework versions, Minitest or RSpec, and the project's data setup and cleanup strategy. Use the existing runner and dependency environment; a testing task does not imply a framework migration.

For Rails applications, read [Rails testing](references/rails.md). For version-sensitive helper behavior, consult documentation matching the locked gem version. The current Rails guide is a source for Rails guidance, not a specification for plain Ruby or RSpec.

## Plain Ruby and shared conventions

- Exercise ordinary Ruby objects directly when their contract does not require application boot or persistence. Load the project's existing helper needed for that test level.
- Make Ruby value distinctions explicit when relevant: `nil`, `false`, empty collections, and absent hash keys can produce different behavior. Cover symbol versus string keys, keyword arguments, encoding, or mutation only when the input contract makes them meaningful.
- Use minimal fixtures or factories following the suite's convention. Keep the attributes that cause the behavior visible in the test. Build objects when persistence is irrelevant; persist them when database behavior is part of the claim.
- Prefer an injected object implementing the needed protocol for a boundary double. With RSpec, use verifying doubles when available. Scope stubs to the example and use the suite's cleanup hooks for environment variables, constants, and class-level state.
- In RSpec, make setup that must occur before the action explicit. Inspect lazy helper evaluation when records or other side effects unexpectedly occur inside an expectation. Keep database writes out of shared context setup unless its cleanup is explicitly supported.
- Check an error's class and relevant attributes. Match the message exactly only when its text is part of the public contract.

## Validation

Use the project's command to select the changed test first, then the affected suite. Check runner help for supported filters and seed options instead of transferring flags between Minitest, Rails, and RSpec. Record the seed for order-dependent failures and verify the repair with the failing order.

Report which test levels actually ran and any unavailable database, browser, or service that prevented validation.
