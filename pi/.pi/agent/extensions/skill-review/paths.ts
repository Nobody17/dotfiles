import {
  existsSync,
  readFileSync,
  readdirSync,
  realpathSync,
  statSync,
} from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join, relative, resolve, sep } from "node:path";

// ── Directory helpers ──────────────────────────────────────────────

export function piDir(): string {
  return process.env.PI_CODING_AGENT_DIR ?? join(homedir(), ".pi", "agent");
}

export const SKILL_CREATION_DIR = join(piDir(), "skills", "skill-creation");

export function scriptPath(name: string): string {
  return join(SKILL_CREATION_DIR, "scripts", name);
}

export function expandHome(pathValue: string): string {
  if (pathValue === "~") return homedir();
  if (pathValue.startsWith("~/")) return join(homedir(), pathValue.slice(2));
  return pathValue;
}

export function resolvePathArg(rawPath: string, cwd: string): string {
  const expandedPath = expandHome(rawPath.trim());
  return expandedPath.startsWith("/") ? expandedPath : resolve(cwd, expandedPath);
}

// ── Skill discovery ───────────────────────────────────────────────

const IGNORED_DIRECTORY_NAMES = new Set([
  ".git",
  ".hg",
  ".svn",
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache",
  "__pycache__",
  "node_modules",
]);

function directoryRealPath(pathValue: string): string | null {
  try {
    const pathStat = statSync(pathValue);
    if (!pathStat.isDirectory()) return null;
    return realpathSync(pathValue);
  } catch {
    return null;
  }
}

function isInsidePath(candidatePath: string, parentPath: string): boolean {
  const relativePath = relative(parentPath, candidatePath);
  return relativePath === "" || (!relativePath.startsWith("..") && !relativePath.startsWith(sep));
}

function relativeSegments(rootDir: string, candidatePath: string): string[] {
  const relativePath = relative(rootDir, candidatePath);
  if (!relativePath || relativePath === ".") return [];
  return relativePath.split(/[\\/]+/).filter(Boolean);
}

function isIgnoredGeneratedSkillArea(rootDir: string, candidatePath: string): boolean {
  const segments = relativeSegments(rootDir, candidatePath);
  for (let segmentIndex = 0; segmentIndex < segments.length - 1; segmentIndex++) {
    if (segments[segmentIndex] !== "evals") continue;
    const nextSegment = segments[segmentIndex + 1];
    if (nextSegment === "fixtures" || nextSegment === "runs") return true;
  }
  return false;
}

function shouldDescendIntoDirectory(rootDir: string, candidatePath: string): boolean {
  if (IGNORED_DIRECTORY_NAMES.has(basename(candidatePath))) return false;
  if (isIgnoredGeneratedSkillArea(rootDir, candidatePath)) return false;
  return true;
}

/** Recursively discover skills under a directory, returning absolute paths. */
function discoverSkillsUnder(rootDir: string): string[] {
  if (!existsSync(rootDir)) return [];
  const skills: string[] = [];
  const visitedDirs = new Set<string>();

  try {
    const stack: string[] = [rootDir];
    while (stack.length > 0) {
      const currentDir = stack.pop()!;
      if (!shouldDescendIntoDirectory(rootDir, currentDir)) continue;

      const currentRealPath = directoryRealPath(currentDir);
      if (!currentRealPath || visitedDirs.has(currentRealPath)) continue;
      visitedDirs.add(currentRealPath);

      if (existsSync(join(currentDir, "SKILL.md"))) {
        skills.push(currentDir);
        // A real skill root may contain fixtures or examples. Do not offer nested
        // SKILL.md files from inside it as separate review targets.
        continue;
      }

      for (const entry of readdirSync(currentDir, { withFileTypes: true })) {
        const entryPath = join(currentDir, entry.name);
        if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;
        if (!shouldDescendIntoDirectory(rootDir, entryPath)) continue;
        stack.push(entryPath);
      }
    }
  } catch {
    // Permission errors, broken symlinks, etc. should not break command startup.
  }
  return skills;
}

function nearestProjectSkillDirs(cwd: string): string[] {
  const dirs: string[] = [];
  let currentDir = resolve(cwd);

  while (true) {
    const piSkills = join(currentDir, ".pi", "skills");
    if (existsSync(piSkills)) dirs.push(piSkills);

    const agentsSkills = join(currentDir, ".agents", "skills");
    if (existsSync(agentsSkills)) dirs.push(agentsSkills);

    if (existsSync(join(currentDir, ".git"))) break;
    const parentDir = dirname(currentDir);
    if (parentDir === currentDir) break;
    currentDir = parentDir;
  }

  return dirs;
}

/** Discover all skills from agent, user, and project directories. Deduplicates by realpath. */
export function discoverSkills(cwd?: string): string[] {
  const agentDir = piDir();
  const effectiveCwd = cwd ?? process.cwd();
  const dirs: string[] = [
    join(agentDir, "skills"),
    join(homedir(), ".agents", "skills"),
    ...nearestProjectSkillDirs(effectiveCwd),
  ];

  const seenRootDirs = new Set<string>();
  const seenRealpaths = new Set<string>();
  const skills: string[] = [];

  for (const dir of dirs) {
    const rootRealPath = directoryRealPath(dir);
    if (!rootRealPath || seenRootDirs.has(rootRealPath)) continue;
    seenRootDirs.add(rootRealPath);

    for (const skill of discoverSkillsUnder(dir)) {
      const skillRealPath = realpathSync(skill);
      if (!seenRealpaths.has(skillRealPath)) {
        seenRealpaths.add(skillRealPath);
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
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const entryPath = join(runsDir, entry.name);
      return { path: entryPath, mtimeMs: statSync(entryPath).mtimeMs, name: entry.name };
    })
    .sort((leftEntry, rightEntry) => {
      const mtimeDelta = rightEntry.mtimeMs - leftEntry.mtimeMs;
      return mtimeDelta !== 0 ? mtimeDelta : rightEntry.name.localeCompare(leftEntry.name);
    });
  return entries.length > 0 ? entries[0].path : null;
}

export function isRunDirForSkill(runDir: string, skillDir: string): boolean {
  try {
    const runRealPath = realpathSync(runDir);
    const runsRootRealPath = realpathSync(join(skillDir, "evals", "runs"));
    return dirname(runRealPath) === runsRootRealPath;
  } catch {
    return false;
  }
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
      .filter((entry) => entry.isFile() && (!extension || entry.name.endsWith(extension)))
      .map((entry) => entry.name);
  } catch {
    return [];
  }
}

/** Resolve a skill-dir argument: expand ~, resolve relative to cwd. */
export function resolveSkillDir(
  raw: string | undefined,
  cwd: string,
): string | null {
  if (!raw?.trim()) return null;
  return resolvePathArg(raw, cwd);
}

function skillSourceLabel(skillPath: string, cwd?: string): string {
  const resolvedSkillPath = resolve(skillPath);
  const agentSkills = resolve(join(piDir(), "skills"));
  const userSkills = resolve(join(homedir(), ".agents", "skills"));
  const projectDirs = nearestProjectSkillDirs(cwd ?? process.cwd()).map((dir) => resolve(dir));

  if (isInsidePath(resolvedSkillPath, agentSkills)) return "agent";
  if (isInsidePath(resolvedSkillPath, userSkills)) return "user";
  if (projectDirs.some((projectDir) => isInsidePath(resolvedSkillPath, projectDir))) return "project";
  return "external";
}

/** Build disambiguated labels for a skill select dialog. */
export function buildSkillLabels(
  skills: string[],
  cwd?: string,
): { labels: string[]; labelToPath: Map<string, string> } {
  const labels: string[] = [];
  const labelToPath = new Map<string, string>();

  for (const skillPath of skills) {
    const name = basename(skillPath);
    const source = skillSourceLabel(skillPath, cwd);
    const label = `${name} [${source}] — ${skillPath}`;
    labelToPath.set(label, skillPath);
    labels.push(label);
  }
  return { labels, labelToPath };
}
