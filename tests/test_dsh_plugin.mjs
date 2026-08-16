import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

import { apply, inject, loadBundledSkill, name } from '../dsh-plugin.js'

const packageJson = JSON.parse(
  readFileSync(new URL('../package.json', import.meta.url), 'utf8'),
)

test('declares an installable DeepSeek Harness bundle', () => {
  assert.equal(packageJson.name, 'dsh-tizhuang-question-bank')
  assert.equal(packageJson.dsh.bundle.patch, './cordis.patch.yml')
  assert.ok(packageJson.keywords.includes('dsh-plugin'))
  assert.deepEqual(inject, ['skills'])
  assert.equal(name, 'tizhuang-question-bank-dsh')

  const patch = readFileSync(new URL('../cordis.patch.yml', import.meta.url), 'utf8')
  assert.match(patch, /id: tizhuang-question-bank/)
  assert.match(patch, /name: dsh-tizhuang-question-bank/)
})

test('loads the existing question-bank skill with its resource directory', () => {
  const skill = loadBundledSkill()

  assert.equal(skill.name, 'question-bank')
  assert.match(skill.description, /K12/)
  assert.match(skill.content, /^# Question Bank/)
  assert.doesNotMatch(skill.content, /^---/)
  assert.equal(skill.source, 'bundled')
  assert.equal(skill.resourceBase.kind, 'directory')
  assert.ok(existsSync(skill.path))
  assert.ok(existsSync(`${skill.resourceBase.path}scripts/question_bank.py`))
  assert.ok(existsSync(`${skill.resourceBase.path}references/api.md`))
})

test('registers the skill and returns the registry disposer', () => {
  let registered
  const dispose = () => {}
  const result = apply({
    skills: {
      register(skill) {
        registered = skill
        return dispose
      },
    },
  })

  assert.equal(result, dispose)
  assert.equal(registered.name, 'question-bank')
  assert.equal(registered.resourceBase.kind, 'directory')
})
