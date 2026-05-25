---
name: homeassistant
description: 'Use when, and only when, the user is working on Home Assistant (HA) home-automation platform YAML/code/config tasks, not general smart-home advice. Always use before answering when the user asks to create, fix, debug, review, or validate HA automations, trigger/condition/action syntax, scripts/sequences, scenes, blueprints, packages, configuration.yaml, secrets, Jinja templates/template sensors, service/action calls, events, entity states/attributes, or repo edits. Use even for one automation/template snippet because current HA syntax differs from legacy examples. Never use for generic household/personal "home assistant" apps, hardware shopping or Zigbee/Z-Wave/Matter device/coordinator recommendations unless HA config/code is requested, Google/Alexa/Siri-only routines, UI-only Home Assistant support with no code/config, or non-HA YAML such as Docker Compose/Kubernetes/GitHub Actions.'
---

# Home Assistant

## Gotchas

- Prefer the current Home Assistant YAML style from the docs: automations use `triggers`, `conditions`, and `actions`; reusable scripts use a top-level `sequence:`. Service/action calls inside sequences are steps like `- action: light.turn_on` with `target:` and `data:`.
- Quote state strings such as `"on"`, `"off"`, `"home"`, and `"not_home"`; YAML booleans otherwise change their meaning.
- Entity states are text. For math or numeric comparisons in templates, convert with `| int(default)` or `| float(default)` and handle `unknown`/`unavailable` with `has_value()` or explicit fallbacks.
- Multiple triggers are OR; multiple conditions are AND by default. Numeric state triggers fire only when a value crosses the threshold, not whenever it remains inside the range.
- Limited templates in trigger setup/`trigger_variables` cannot use most state-reading helpers and are evaluated when the trigger is attached, not for every event.
- Blueprint inputs use `!input name` in YAML, but templates need those inputs exposed through `variables:` first. Input sections require `homeassistant.min_version: 2024.6.0` or newer.
- `automations.yaml` is UI-managed. Do not edit it unless the user explicitly asks; for hand-written YAML prefer labeled `automation ...:` blocks, packages, or files included from `configuration.yaml`.
- Use `!secret` for tokens/passwords. When splitting config, included files contain only the nested content for their include point, not the parent key again.

## Workflow

1. Identify the code surface: automation, script, scene, blueprint, template entity, integration YAML, package, dashboard YAML, or repository files.
2. Inspect existing files before changing style. Preserve the user's organization, entity IDs, helper names, and UI-managed/generated sections unless asked to refactor them.
3. Use Home Assistant runtime facts instead of guessing: ask for or inspect Developer Tools > States/Actions/Events output when entity IDs, attributes, action fields, or event payloads matter.
4. Draft the smallest working YAML/template. Include stable `alias` values and automation `id` values when producing YAML automations so traces/UI debugging work.
5. For templates, test the expression in isolation: define missing `trigger`, `this`, `value`, or `value_json` sample data, verify types, then paste the final quoted or block-scalar YAML.
6. For large configurations, prefer packages or `!include` files by feature/area. Keep `auth_providers` in `configuration.yaml`; package keys that identify entities must stay unique.
7. Validate before recommending reload/restart, then summarize changed files, reload scope, and any assumptions about live entities or integrations.

## Validation

- YAML/config: run the Home Assistant CLI when available, or use Developer Tools > YAML > Check configuration.

  ```bash
  hass --script check_config -c <config-dir> --fail-on-warnings
  ```

- Automations: use Run actions only for the action sequence; use Developer Tools > Actions > `automation.trigger` when conditions should be tested. Check traces after a real or test run.
- Templates: use Developer Tools > Template; if a value comes from an incoming payload, add `{% set value_json = ... %}` or `{% set value = ... %}` test data first.
- Events/actions: use Developer Tools > Events to capture event payloads and Developer Tools > Actions to confirm the action name and required `target`/`data` fields.
- After valid config, reload the specific YAML integration if listed in Developer Tools > YAML; otherwise restart Home Assistant.

## References

- Read `references/code-patterns.md` for deeper examples of automations, scripts, packages, scenes, blueprints, and templates.
- Read `references/docs-map.md` when a task needs the source documentation path for a specific Home Assistant topic.

<!--
Source references:
- /home/yorunai/programming/skill_creation/homeassistant/docs/automation/yaml.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/automation/trigger.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/automation/action.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/templating/states.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/configuration/yaml.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/tools/check_config.markdown
-->
