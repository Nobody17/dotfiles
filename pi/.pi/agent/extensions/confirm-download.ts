/**
 * Confirm Download Extension
 *
 * Asks for confirmation whenever the agent tries to download files
 * from the web via bash (curl, wget, aria2c, axel, yt-dlp, etc.).
 * Pipe-to-shell gets a more aggressive warning.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// ── Patterns ────────────────────────────────────────────────────────

/** Patterns that are always dangerous regardless of filename */
const alwaysRiskyPatterns: RegExp[] = [
  // Piped to shell interpreter
  /\|\s*(sh|bash|zsh|fish|dash|csh|python|python3|perl|ruby|lua|node|pwsh)(\s|$)/,
  // curl/wget eval pattern
  /\bcurl\b[^|]*\|\s*\b(bash|sh|sudo\s+(bash|sh))\b/,
];

/** Bash commands that download from the web */
const downloadCommands: { pattern: RegExp; requireOutputFlag?: boolean }[] = [
  { pattern: /\bcurl\b/, requireOutputFlag: true },
  { pattern: /\bwget\b/ },
  { pattern: /\baria2c?\b/ },
  { pattern: /\baxel\b/ },
  { pattern: /\byt-dlp?\b/ },
  { pattern: /\byoutube-dl\b/ },
];

// ── Helpers ─────────────────────────────────────────────────────────

function extractUrls(command: string): string[] {
  const urls: string[] = [];
  const patterns = [/https?:\/\/[^\s"'`<>|;&]+/g, /ftp:\/\/[^\s"'`<>|;&]+/g];
  for (const pattern of patterns) {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(command)) !== null) {
      const url = match[0].replace(/[.,;:!'")\]}>]$/, "");
      if (!urls.includes(url)) urls.push(url);
    }
  }
  return urls;
}

function hasOutputFlag(command: string): boolean {
  return /(?:-o|--output|-O|--remote-name)\b/.test(command) || />\s*\S/.test(command);
}

function filenameFromUrl(url: string): string {
  try {
    const parts = new URL(url).pathname.split("/");
    const last = parts[parts.length - 1];
    if (last.length > 0) return decodeURIComponent(last);
  } catch { /* fall through to regex */ }
  const match = url.match(/\/([^/?#]+)(?:[?#]|$)/);
  return match ? decodeURIComponent(match[1]) : url;
}

function isAlwaysRisky(command: string): boolean {
  return alwaysRiskyPatterns.some((p) => p.test(command));
}

// ── Extension ───────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;

    const command = event.input.command as string;

    // Match against download commands
    let matched: (typeof downloadCommands)[number] | undefined;
    for (const dc of downloadCommands) {
      if (dc.pattern.test(command)) {
        matched = dc;
        break;
      }
    }
    if (!matched) return undefined;

    // For curl without output flags: skip (just API calls / viewing)
    if (matched.requireOutputFlag && !hasOutputFlag(command)) {
      return undefined;
    }

    if (!ctx.hasUI) {
      return { block: true, reason: "Download blocked (no UI for confirmation)" };
    }

    // Pipe to shell — more aggressive prompt
    if (isAlwaysRisky(command)) {
      const choice = await ctx.ui.select(
        `🚫 Pipe to shell detected!\n\n  ${command}\n\nThis would execute downloaded code immediately.\n\nAllow?`,
        ["No, block it", "Yes, run it"],
      );
      if (choice !== "Yes, run it") {
        return { block: true, reason: "Pipe to shell blocked by user" };
      }
      return undefined;
    }

    // Regular download — always ask
    const urls = extractUrls(command);
    const urlInfo =
      urls.length > 0
        ? `\n\nFiles:\n${urls.map((u) => `  • ${filenameFromUrl(u)}`).join("\n")}`
        : "";

    const choice = await ctx.ui.select(
      `💻 Download from web?\n\n  ${command}${urlInfo}\n\nAllow?`,
      ["Yes, download", "No, block it"],
    );

    if (choice !== "Yes, download") {
      return { block: true, reason: "Download blocked by user" };
    }

    return undefined;
  });
}
