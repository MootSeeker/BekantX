// PostToolUse (Edit|Write): after a KiCad file was edited, run ERC (schematic) or DRC (board) and
// report the violation counts back to Claude as additional context. Never blocks.
import { readFileSync, readdirSync, mkdtempSync, rmSync, existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { join, dirname, basename, extname } from 'node:path'

const input = JSON.parse(readFileSync(0, 'utf8'))
const file = String(input.tool_input?.file_path ?? '')
const ext = extname(file)
if (!['.kicad_sch', '.kicad_pcb'].includes(ext) || !existsSync(file)) process.exit(0)

const cliCandidates = [
  'C:\\Program Files\\KiCad\\10.0\\bin\\kicad-cli.exe',
  'C:\\Program Files\\KiCad\\9.0\\bin\\kicad-cli.exe',
  'kicad-cli',
]
const cli = cliCandidates.find((c) => c === 'kicad-cli' || existsSync(c))

const report = (text) => {
  process.stdout.write(
    JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: text } }),
  )
  process.exit(0)
}

// ERC must run on the root sheet: the one that shares its name with the .kicad_pro in the same folder.
let target = file
let kind = 'drc'
if (ext === '.kicad_sch') {
  kind = 'erc'
  const dir = dirname(file)
  const pro = readdirSync(dir).find((f) => f.endsWith('.kicad_pro'))
  if (pro) {
    const root = join(dir, basename(pro, '.kicad_pro') + '.kicad_sch')
    if (existsSync(root)) target = root
  }
}

const tmp = mkdtempSync(join(tmpdir(), 'kicad-check-'))
try {
  const out = join(tmp, `${kind}.json`)
  const args = kind === 'erc'
    ? ['sch', 'erc', '--format', 'json', '--severity-all', '-o', out, target]
    : ['pcb', 'drc', '--format', 'json', '--severity-all', '--schematic-parity', '-o', out, target]
  let r = spawnSync(cli, args, { encoding: 'utf8', timeout: 100000 })
  if (!existsSync(out) && kind === 'drc') {
    // parity check needs a schematic; retry without it
    r = spawnSync(cli, args.filter((a) => a !== '--schematic-parity'), { encoding: 'utf8', timeout: 100000 })
  }
  if (!existsSync(out)) report(`KiCad ${kind.toUpperCase()} could not run on ${basename(target)}: ${(r.stderr || r.stdout || 'no output').trim().slice(0, 300)}`)

  const data = JSON.parse(readFileSync(out, 'utf8'))
  const items = kind === 'erc'
    ? (data.sheets ?? []).flatMap((s) => s.violations ?? [])
    : [...(data.violations ?? []), ...(data.unconnected_items ?? []), ...(data.schematic_parity ?? [])]
  const count = {}
  for (const v of items) count[v.severity ?? 'unknown'] = (count[v.severity ?? 'unknown'] ?? 0) + 1
  const typeCount = {}
  for (const v of items) typeCount[v.type] = (typeCount[v.type] ?? 0) + 1
  const top = Object.entries(typeCount).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([t, n]) => `${t} x${n}`).join(', ')
  const summary = items.length === 0
    ? 'clean (0 violations)'
    : `${items.length} violations (${Object.entries(count).map(([s, n]) => `${s}: ${n}`).join(', ')}); top: ${top}`
  report(`KiCad ${kind.toUpperCase()} on ${basename(target)} after editing ${basename(file)}: ${summary}. Report this result to the user; fix errors you introduced.`)
} catch (e) {
  report(`KiCad check failed to evaluate: ${String(e.message).slice(0, 200)}`)
} finally {
  rmSync(tmp, { recursive: true, force: true })
}
