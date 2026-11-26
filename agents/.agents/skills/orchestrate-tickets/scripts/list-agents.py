#!/usr/bin/env python3
"""Print name, status, tab and pane of the Herdr agents of one run prefix, one line each."""
import argparse
import json
import subprocess


def agent_lines(agents, prefix):
    matching = [agent for agent in agents if str(agent.get("name", "")).startswith(prefix)]
    return [
        f'{agent["name"]}\t{agent.get("agent_status", "?")}\t{agent.get("tab_id", "?")}\t{agent.get("pane_id", "?")}'
        for agent in sorted(matching, key=lambda agent: agent["name"])
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True, help="run prefix of the agent names, for example dg-")
    arguments = parser.parse_args()
    output = subprocess.run(["herdr", "agent", "list"], check=True, capture_output=True, text=True).stdout
    agents = json.loads(output, strict=False)["result"]["agents"]
    lines = agent_lines(agents, arguments.prefix)
    print("\n".join(lines) if lines else f"no agent with prefix {arguments.prefix}")


if __name__ == "__main__":
    main()
