#!/usr/bin/env python3
"""Write an assignment file from a run-owned template and the ledger.

Usage: render-assignment.py <template> <output> --ledger <ledger.json> [--ticket <id>] [--set key=value ...]

The template marks a value as {{dotted.path}}. The roots are:
  ledger    the whole ledger
  ticket    ledger.tickets.<id> (with --ticket)
  run       the directory of the ledger
  <key>     each --set value
A path that does not resolve stops the script, and it writes no file.
Keep one template per role (worker, integrator) in <run>/assignments/templates/.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r'\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}')


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('template', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--ticket')
    parser.add_argument('--set', action='append', default=[], metavar='KEY=VALUE')
    return parser.parse_args()


def resolve(context, dotted_path):
    value = context
    for part in dotted_path.split('.'):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError(dotted_path)
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def render(template, context):
    missing = sorted({match.group(1) for match in PLACEHOLDER.finditer(template) if not resolvable(context, match.group(1))})
    if missing:
        raise KeyError(', '.join(missing))
    return PLACEHOLDER.sub(lambda match: resolve(context, match.group(1)), template)


def resolvable(context, dotted_path):
    try:
        resolve(context, dotted_path)
        return True
    except KeyError:
        return False


def main():
    arguments = parse_arguments()
    ledger_path = arguments.ledger.resolve()
    ledger = json.loads(ledger_path.read_text())
    context = {'ledger': ledger, 'run': str(ledger_path.parent)}
    if arguments.ticket is not None:
        context['ticket'] = ledger['tickets'][arguments.ticket]
    for assignment in arguments.set:
        key, separator, value = assignment.partition('=')
        if not separator:
            sys.exit(f'--set needs KEY=VALUE: {assignment}')
        context[key] = value
    try:
        text = render(arguments.template.read_text(), context)
    except KeyError as error:
        sys.exit(f'unresolved placeholders: {error.args[0]}')
    arguments.output.write_text(text)
    print(arguments.output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
