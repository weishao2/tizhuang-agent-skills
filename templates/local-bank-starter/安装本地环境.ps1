[CmdletBinding()]
param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskRuntime = Join-Path $taskRoot '.runtime'
$taskPython = Join-Path $taskRuntime 'Scripts/python.exe'
$taskRequirements = Join-Path $taskRoot 'skills/tizhuang-local-bank/scripts/requirements.txt'
$taskSettings = Join-Path $taskRoot '题庄本地题库/.obsidian/plugins/tizhuang-question-bank/data.json'
if (-not (Test-Path -LiteralPath $taskRequirements)) { throw '请先完整解压初始体验包，再运行此脚本。' }
& $PythonExecutable -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
if ($LASTEXITCODE -ne 0) { throw '请安装 Python 3.10 或更高版本，或通过 -PythonExecutable 指定 Python 路径。' }
if (-not (Test-Path -LiteralPath $taskPython)) {
    & $PythonExecutable -m venv $taskRuntime
    if ($LASTEXITCODE -ne 0) { throw '独立 Python 环境创建失败。' }
}
& $taskPython -m pip install -r $taskRequirements
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络后重试；尚未更新插件设置。' }
$taskData = if (Test-Path -LiteralPath $taskSettings) { Get-Content -LiteralPath $taskSettings -Encoding UTF8 -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (Test-Path -LiteralPath $taskSettings) {
    Copy-Item -LiteralPath $taskSettings -Destination ($taskSettings + '.before-python-' + (Get-Date -Format 'yyyyMMddHHmmss'))
}
$taskData | Add-Member -NotePropertyName pythonPath -NotePropertyValue $taskPython -Force
[IO.File]::WriteAllText($taskSettings, ($taskData | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
Write-Output '已配置独立本地环境。请重新打开 Obsidian 题库；可以开始 PDF 准备与 Word 组卷。'
