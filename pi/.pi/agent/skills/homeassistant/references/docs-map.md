# Home Assistant Docs Map

Use this reference to pick the source document to read from the local Home Assistant documentation corpus when a task needs details beyond the skill.

Source corpus: `/home/yorunai/programming/skill_creation/homeassistant/docs/`

## Core code topics

- Automations overview and YAML schema: `automation.markdown`, `automation/yaml.markdown`
- Automation triggers: `automation/trigger.markdown`
- Automation conditions: `automation/condition.markdown` and `scripts/conditions.markdown`
- Automation actions and script syntax: `automation/action.markdown`, `scripts.markdown`, `scripts/perform-actions.markdown`
- Automation modes and troubleshooting: `automation/modes.markdown`, `automation/troubleshooting.markdown`
- Templates: `templating.markdown`, `templating/where-to-use.markdown`, `templating/states.markdown`, `templating/yaml.markdown`, `templating/debugging.markdown`, `templating/errors.markdown`, `templating/patterns.markdown`
- Configuration YAML: `configuration.markdown`, `configuration/yaml.markdown`, `configuration/troubleshooting.markdown`
- Splitting, packages, and secrets: `configuration/splitting_configuration.markdown`, `configuration/packages.markdown`, `configuration/secrets.markdown`
- Blueprints: `blueprint.markdown`, `blueprint/schema.markdown`, `blueprint/selectors.markdown`, `blueprint/tutorial.markdown`
- Scenes: `scene.markdown`
- Events and state objects: `configuration/events.markdown`, `configuration/state_object.markdown`
- Developer tools and config check: `tools/dev-tools.markdown`, `tools/check_config.markdown`

## Reading strategy

1. Read the narrow page for the requested feature first, not the whole corpus.
2. Pull exact YAML keys and validation commands from docs, then synthesize; do not copy prose into the skill response.
3. If docs conflict with existing user files, preserve valid user style unless the user asked for modernization; point out current-docs style separately.
4. For integration-specific fields not present in this corpus, ask for the integration docs, current UI action schema, or Developer Tools output rather than inventing fields.

<!--
Source references:
- /home/yorunai/programming/skill_creation/homeassistant/docs/
-->
