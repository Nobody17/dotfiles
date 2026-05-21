import {
  existsSync,
  readFileSync,
  readdirSync,
  realpathSync,
  statSync,
} from "node:fs";
import { homedir } from "node:os";
import { join, basename } from "node:path";

// ── Directory helpers ──────────────────────────────────────────────

export function piDir(): string {
  return process.env.PI_CODING_AGENT_DIR ?? join(homedir(), ".pi", "agent");
}

export const SKILL_CREATION_DIR = join(piDir(), "skills", "skill-creation");

export function scriptPath(name: string): string {
  return join(SKILL_CREATION_DIR, "scripts", name);
}

// ── Skill discovery ───────────────────────────────────────────────

function directoryRealPath(path: string): string | null {
  try {
    const stat = statSync(path);
    if (!stat.isDirectory()) return null;
    return realpathSync(path);
  } catch {
    return null;
  }
}

/** Recursively discover skills under a directory, returning absolute paths. */
function discoverSkillsUnder(dir: string): string[] {
  if (!existsSync(dir)) return [];
  const skills: string[] = [];
  const visitedDirs = new Set<string>();

  try {
    const stack: string[] = [dir];
    while (stack.length > 0) {
      const current = stack.pop()!;
      const currentRealPath = directoryRealPath(current);
      if (!currentRealPath || visitedDirs.has(currentRealPath)) continue;
      visitedDirs.add(currentRealPath);

      if (existsSync(join(current, "SKILL.md"))) {
        skills.push(current);
      }

      for (const entry of readdirSync(current, { withFileTypes: true })) {
        const full = join(current, entry.name);
        if (entry.isDirectory() || entry.isSymbolicLink()) {
          stack.push(full);
        }
      }
    }
  } catch {
    // Permission errors, etc.
  }
  return skills;
}

/** Discover all skills from agent, user, and project directories. Deduplicates by realpath. */
export function discoverSkills(cwd?: string): string[] {
  const agentDir = piDir();
  const dirs: string[] = [
    join(agentDir, "skills"),
    join(homedir(), ".agents", "skills"),
  ];
  const effectiveCwd = cwd ?? process.cwd();
  const projectSkills = join(effectiveCwd, ".pi", "skills");
  if (existsSync(projectSkills)) dirs.push(projectSkills);
  const agentsSkills = join(effectiveCwd, ".agents", "skills");
  if (existsSync(agentsSkills)) dirs.push(agentsSkills);

  const seenRealpaths = new Set<string>();
  const skills: string[] = [];
  for (const dir of dirs) {
    for (const skill of discoverSkillsUnder(dir)) {
      const real = realpathSync(skill);
      if (!seenRealpaths.has(real)) {
        seenRealpaths.add(real);
        skills.push(skill);
      }
    }
  }
  return skills.sort();
}

// ── Run directory ──────────────────────────────────────────────────

export function findLatestRunDir(skillDir: string): string | null {
  const runsDir = join(skillDir, "evals", "runs");
  if (!existsSync(runsDir)) return null;
  const entries = readdirSync(runsDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort()
    .reverse();
  return entries.length > 0 ? join(runsDir, entries[0]) : null;
}

// ── File utilities ─────────────────────────────────────────────────

export function safeReadFile(filePath: string): string | null {
  if (!existsSync(filePath)) return null;
  try {
    return readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

export function listDirFiles(dir: string, extension?: string): string[] {
  if (!existsSync(dir)) return [];
  try {
    return readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.isFile() && (!extension || e.name.endsWith(extension)))
      .map((e) => e.name);
  } catch {
    return [];
  }
}

/** Resolve a skill-dir argument: expand ~, resolve relative to cwd. */
export function resolveSkillDir(
  raw: string | undefined,
  cwd: string,
): string | null {
  if (!raw) return null;
  if (raw.startsWith("~")) return join(homedir(), raw.slice(1));
  if (raw.startsWith("/")) return raw;
  return join(cwd, raw);
}

/** Build disambiguated labels for a skill select dialog. */
export function buildSkillLabels(
  skills: string[],
): { labels: string[]; labelToPath: Map<string, string> } {
  const nameCounts = new Map<string, number>();
  for (const skillPath of skills) {
    const name = basename(skillPath);
    nameCounts.set(name, (nameCounts.get(name) ?? 0) + 1);
  }

  const labels: string[] = [];
  const labelToPath = new Map<string, string>();
  for (const skillPath of skills) {
    const name = basename(skillPath);
    let label =
      (nameCounts.get(name) ?? 0) > 1
        ? `${name} (${basename(join(skillPath, ".."))})`
        : name;
    if (labelToPath.has(label)) {
      label = `${label} [${skillPath}]`;
    }
    labelToPath.set(label, skillPath);
    labels.push(label);
  }
  return { labels, labelToPath };
}
