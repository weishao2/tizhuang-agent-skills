[CmdletBinding()]
param(
    [string]$VaultPath,
    [string]$SkillDirectory,
    [ValidateSet('codex')][string]$Agent,
    [string]$PythonExecutable = 'python',
    [switch]$Plan,
    [switch]$SkipSkill
)
$ErrorActionPreference = 'Stop'
$taskInstaller = Join-Path $PSScriptRoot 'skills/tizhuang-local-bank/scripts/install_local_bank.py'
$taskArguments = @($taskInstaller, '--package', $PSScriptRoot)
if ($VaultPath) { $taskArguments += @('--vault', $VaultPath) }
if ($SkipSkill) { $taskArguments += '--skip-skill' }
elseif ($SkillDirectory) { $taskArguments += @('--skill-dir', $SkillDirectory) }
elseif ($Agent) { $taskArguments += @('--agent', $Agent) }
else { throw '请由当前 Agent 指定 SkillDirectory；Codex 可用 -Agent codex；只装插件可用 -SkipSkill。' }
if ($Plan) { $taskArguments += '--plan' } else { $taskArguments += '--apply' }
& $PythonExecutable @taskArguments
exit $LASTEXITCODE
