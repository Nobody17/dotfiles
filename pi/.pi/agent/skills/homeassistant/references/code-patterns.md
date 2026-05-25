# Home Assistant Code Patterns

Use this only when `SKILL.md` is not enough detail for a Home Assistant code task.

## Contents

- [Automation pattern](#automation-pattern)
- [Script and template patterns](#script-and-template-patterns)
- [Splitting configuration and packages](#splitting-configuration-and-packages)
- [Blueprints, scenes, and events](#blueprints-scenes-and-events)
- [Debugging checklist](#debugging-checklist)

## Automation pattern

```yaml
automation hallway_motion_lights:
  - id: hallway_motion_lights_after_dark
    alias: "Hallway motion lights after dark"
    mode: restart
    triggers:
      - trigger: state
        entity_id: binary_sensor.hallway_motion
        to: "on"
        id: motion_on
    conditions:
      - condition: numeric_state
        entity_id: sun.sun
        attribute: elevation
        below: 4
    actions:
      - action: light.turn_on
        target:
          entity_id: light.hallway
        data:
          brightness_pct: 60
      - wait_for_trigger:
          - trigger: state
            entity_id: binary_sensor.hallway_motion
            to: "off"
            for: "00:02:00"
        timeout: "00:10:00"
        continue_on_timeout: true
      - action: light.turn_off
        target:
          entity_id: light.hallway
```

Notes:

- Pick `mode` deliberately: `single` throttles, `restart` restarts long waits, `queued` serializes devices that cannot handle overlap, and `parallel` allows independent concurrent runs.
- Put conditions before actions for run gating; put `condition:` steps inside `actions` only when the sequence should stop partway through.
- Use trigger `id` values when one automation handles several trigger causes.

## Script and template patterns

```yaml
script:
  announce_open_windows:
    alias: "Announce open windows"
    sequence:
      - variables:
          open_windows: >-
            {{ states.binary_sensor
               | selectattr('entity_id', 'search', '_window')
               | selectattr('state', 'eq', 'on')
               | map(attribute='name')
               | list }}
      - condition: template
        value_template: "{{ open_windows | count > 0 }}"
      - action: notify.notify
        data:
          message: >-
            Open windows: {{ open_windows | join(', ') }}
```

Template rules that prevent common failures:

- `states('sensor.temperature')` returns text. Use `| float(0)` or `| int(0)` before math.
- Single-line templates in YAML need quotes. Multi-line expressions usually use `>-`; messages that need line breaks use `|`.
- `value` and `value_json` exist only in incoming-data templates such as MQTT/REST; define sample values when testing in Developer Tools > Template.
- `trigger` exists in automations, and `this` exists where Home Assistant knows the current template entity. They are not available in every template editor test.

## Splitting configuration and packages

```yaml
# configuration.yaml
homeassistant:
  packages: !include_dir_named packages
automation manual: !include automations/manual.yaml
script: !include scripts.yaml
```

```yaml
# packages/garage.yaml
input_boolean:
  garage_override:
    name: Garage override
automation:
  - id: garage_notify_left_open
    alias: "Garage left open notification"
    triggers:
      - trigger: state
        entity_id: cover.garage_door
        to: "open"
        for: "00:10:00"
    actions:
      - action: notify.notify
        data:
          message: "Garage door has been open for 10 minutes."
```

Package reminders:

- With `!include`, the included file must contain YAML valid at the include point; do not repeat the parent key unless the include point expects it.
- With `!include_dir_named packages`, each file's basename becomes the package name and must be globally unique across subfolders.
- Platform-style entries (`light`, `switch`, `sensor`, etc.) can merge across packages; entity-keyed helpers need unique keys.
- Keep secrets in `secrets.yaml` and reference them as `!secret name`.

## Blueprints, scenes, and events

- Blueprint inputs use `!input input_name` in YAML. To use an input in a template, first expose it through `variables:` or a `variables` action.
- If a blueprint uses input sections, input names must be globally unique and referenced directly by name (not section name); set `homeassistant.min_version: 2024.6.0` or newer.
- Scenes define target entity states and are activated with `scene.turn_on` or applied ad hoc with `scene.apply`; there is no `scene.turn_off` action.
- Prefer the Home Assistant trigger (`trigger: homeassistant`, `event: start`/`shutdown`) over raw core startup/shutdown events for automations.
- For custom event automations, capture the actual payload in Developer Tools > Events before writing `event_data` filters or `trigger.event.data...` templates.

## Debugging checklist

1. Check YAML parsing and full config validation before restart.
2. Confirm the entity ID, state spelling, and attributes in Developer Tools > States.
3. Confirm action names and accepted fields in Developer Tools > Actions.
4. Test templates with representative sample variables and fallbacks.
5. Trigger automations through the UI or Developer Tools, then inspect traces; YAML automations need `id` values for stored traces.

<!--
Source references:
- /home/yorunai/programming/skill_creation/homeassistant/docs/automation/yaml.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/automation/modes.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/scripts.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/configuration/splitting_configuration.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/configuration/packages.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/blueprint/schema.markdown
- /home/yorunai/programming/skill_creation/homeassistant/docs/scene.markdown
-->
