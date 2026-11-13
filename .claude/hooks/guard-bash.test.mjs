import { test } from 'node:test'
import assert from 'node:assert/strict'
import { check } from './guard-bash.mjs'

const blocked = (cmd, branch = 'feature/x') => assert.ok(check(cmd, branch), `should block: ${cmd}`)
const allowed = (cmd, branch = 'feature/x') => assert.equal(check(cmd, branch), null, `should allow: ${cmd}`)

test('commits on main are blocked, on topic branches allowed', () => {
  blocked('git commit -m "x"', 'main')
  allowed('git commit -m "x"', 'feature/x')
})

test('pushes to main are blocked', () => {
  blocked('git push origin main')
  blocked('git push origin HEAD:main')
  blocked('git push', 'main')
  allowed('git push -u origin feature/x')
  allowed('git push origin feature/x')
})

test('force push and no-verify are blocked', () => {
  blocked('git push --force origin feature/x')
  blocked('git push -f origin feature/x')
  blocked('git commit --no-verify -m "x"')
  blocked('git commit -n -m "x"')
})

test('text inside quotes and heredocs is not a command', () => {
  allowed('git commit -m "docs: explain git push origin main"')
  allowed('git commit -F - <<\'EOF\'\nfix: x\n\ngit push --force\nEOF')
})

test('destructive and merge commands', () => {
  blocked('git reset --hard HEAD~1')
  blocked('gh pr merge 5 --squash')
  blocked('git merge feature/x', 'main')
  allowed('git merge main', 'feature/x')
  allowed('git status && git log --oneline -3', 'main')
})
