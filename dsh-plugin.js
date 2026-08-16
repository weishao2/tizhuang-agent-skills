import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export const name = 'tizhuang-question-bank-dsh'
export const inject = ['skills']

const SKILL_DIRECTORY = new URL('./skills/question-bank/', import.meta.url)
const SKILL_FILE = new URL('SKILL.md', SKILL_DIRECTORY)
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)([\s\S]*)$/
const SKILL_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

function unquote(value) {
  const trimmed = value.trim()
  const quote = trimmed[0]
  if ((quote === '"' || quote === "'") && trimmed.at(-1) === quote) {
    return trimmed.slice(1, -1)
  }
  return trimmed
}

function readFrontmatterField(frontmatter, field) {
  const match = frontmatter.match(new RegExp(`^${field}:\\s*(.+?)\\s*$`, 'm'))
  if (!match) throw new Error(`Bundled question-bank skill is missing ${field}`)
  return unquote(match[1])
}

export function loadBundledSkill() {
  const raw = readFileSync(SKILL_FILE, 'utf8').replace(/^\uFEFF/, '')
  const match = raw.match(FRONTMATTER)
  if (!match) throw new Error('Bundled question-bank SKILL.md has invalid frontmatter')

  const skillName = readFrontmatterField(match[1], 'name')
  const description = readFrontmatterField(match[1], 'description')
  if (!SKILL_NAME.test(skillName)) {
    throw new Error(`Bundled skill name is not kebab-case: ${skillName}`)
  }
  if (!description) throw new Error('Bundled question-bank skill has an empty description')

  return {
    name: skillName,
    description,
    source: 'bundled',
    content: match[2].replace(/^\s+/, ''),
    path: fileURLToPath(SKILL_FILE),
    resourceBase: {
      kind: 'directory',
      path: fileURLToPath(SKILL_DIRECTORY),
    },
  }
}

export function apply(ctx) {
  return ctx.skills.register(loadBundledSkill())
}
