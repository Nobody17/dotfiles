/**
 * last-skill - Shows the last used skill in the footer.
 *
 * Detects skill usage by watching for AI `read` calls on SKILL.md files
 * (how the AI loads skills) and user `/skill:name` commands.
 * Displays the skill name as a persistent status indicator in the footer.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";

const SKILL_COMMAND_RE = /^\/skill:([\w-]+)/;

/** Extract skill name from a SKILL.md path like /path/to/skill-name/SKILL.md */
function extractSkillFromPath(path: string): string | null {
  const match = path.match(/(?:^|\/)([\w-]+)\/SKILL\.md$/i);
  return match ? match[1]! : null;
}

export default function (pi: ExtensionAPI) {
  let lastSkill: string | null = null;

  function showSkill(name: string, ctx: Parameters<Parameters<typeof pi.on>[1]>[1]) {
    lastSkill = name;
    ctx.ui.setStatus("last-skill", ctx.ui.theme.fg("accent", `skill: ${name}`));
  }

  // Detect AI reading a SKILL.md file (how the AI activates skills)
  pi.on("tool_call", (event, ctx) => {
    if (isToolCallEventType("read", event)) {
      const skillName = extractSkillFromPath(event.input.path);
      if (skillName) {
        showSkill(skillName, ctx);
      }
    }
  });

  // Detect user invoking /skill:name commands
  pi.on("input", async (event, ctx) => {
    const match = event.text.match(SKILL_COMMAND_RE);
    if (match) {
      showSkill(match[1]!, ctx);
    }
    return { action: "continue" };
  });

  // Clear on /new or /resume
  pi.on("session_before_switch", async (_event, ctx) => {
    lastSkill = null;
    ctx.ui.setStatus("last-skill", undefined);
  });

  // Restore on /reload
  pi.on("session_start", async (_event, ctx) => {
    if (lastSkill) {
      ctx.ui.setStatus("last-skill", ctx.ui.theme.fg("accent", `skill: ${lastSkill}`));
    }
  });
}
