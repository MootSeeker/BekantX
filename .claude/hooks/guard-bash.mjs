// PreToolUse (Bash): enforces the git rules from CLAUDE.md.
// Only real commands are inspected: heredoc bodies and quoted text are stripped first,
// so commit messages and file contents do not trigger the guard.
import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

/** Returns a reason string if the command violates a rule, otherwise null. */
export function check(cmd, currentBranch) {
  const skeleton = cmd
    .replace(/<<-?[ \t]*(['"]?)(\w+)\1([^\n]*)\n[\s\S]*?\n[ \t]*\2(?!\w)/g, '$3')
    .replace(/'[^']*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""')

  const segments = skeleton
    .split(/&&|\|\||[;|\n]/)
    .map((s) => s.trim().replace(/^(?:\w+=\S*\s+)+/, '').replace(/^[({]\s*/, ''))

  const git = (name) =>
    segments
      .map((s) => s.match(new RegExp(`^git(?:\\s+-\\S+(?:\\s+[^-\\s]\\S*)?)*\\s+${name}\\b(.*)$`))?.[1])
      .filter((rest) => rest !== undefined)

  const protectedBranch = (b) => b === 'main' || b === 'master'

  for (const rest of git('push')) {
    if (/(^|\s)(--force\b|--force-with-lease\b|-f\b|\+\S)/.test(rest))
      return 'No force-push (CLAUDE.md git rule 6).'
    if (/(^|\s)(--delete|-d)\b/.test(rest) && /\b(main|master)\b/.test(rest))
      return 'Do not delete the main branch.'
    const args = rest.trim().split(/\s+/).filter((a) => a && !a.startsWith('-'))
    const refspecs = args.slice(1)
    const toMain = refspecs.some((r) => /(^|:)(refs\/heads\/)?(main|master)$/.test(r))
    const implicitFromMain = refspecs.length === 0 && protectedBranch(currentBranch)
    if (toMain || implicitFromMain)
      return 'No push to main (CLAUDE.md git rule 1). Push a topic branch and open a pull request.'
  }

  for (const rest of git('commit')) {
    if (/--no-verify\b|(^|\s)-[a-zA-Z]*n[a-zA-Z]*(\s|$)/.test(rest))
      return 'No --no-verify (CLAUDE.md git rule 6).'
    if (/--no-gpg-sign\b/.test(rest)) return 'Do not bypass signing (CLAUDE.md git rule 6).'
    if (protectedBranch(currentBranch))
      return 'No commits on main (CLAUDE.md git rule 1). Create a topic branch first: git switch -c <type>/<topic>.'
  }

  for (const rest of git('merge')) {
    if (protectedBranch(currentBranch) && !/--abort|--continue|--quit/.test(rest))
      return 'Do not merge into main locally (CLAUDE.md git rule 5). Merge through a pull request after the user approves.'
  }

  for (const rest of git('rebase')) {
    if (protectedBranch(currentBranch) && !/--abort|--continue|--quit/.test(rest))
      return 'No history rewriting on main (CLAUDE.md git rule 6).'
  }

  if (segments.some((s) => /^git\s+reset\s+.*--hard\b/.test(s)))
    return 'git reset --hard discards work. Ask the user first.'

  if (segments.some((s) => /^gh\s+pr\s+merge\b/.test(s)))
    return 'Merging needs the user\'s explicit OK and green CI (CLAUDE.md git rule 5). Ask first, then run it yourself in the terminal.'

  return null
}

function currentBranch() {
  const r = spawnSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { encoding: 'utf8' })
  return r.status === 0 ? r.stdout.trim() : ''
}

if (process.argv[1]?.endsWith('guard-bash.mjs')) {
  const input = JSON.parse(readFileSync(0, 'utf8'))
  const cmd = String(input.tool_input?.command ?? '')
  const reason = /\bgit\b|\bgh\b/.test(cmd) ? check(cmd, currentBranch()) : null
  if (reason) {
    process.stderr.write(`Blocked (CLAUDE.md, git rules): ${reason}\n`)
    process.exit(2)
  }
}
