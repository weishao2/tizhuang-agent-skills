param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [string]$Python,
    [int]$Port = 4186
)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path $PSScriptRoot -Parent
$workspacePath = [IO.Path]::GetFullPath($Workspace)
$sessionPath = Join-Path $workspacePath 'session.json'
$studioScript = Join-Path $PSScriptRoot 'studio.py'
if (-not $Python) {
    $localPython = Join-Path $skillRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $localPython) { $Python = $localPython }
    else {
        $candidate = Get-Command python -ErrorAction SilentlyContinue
        if ($candidate) { $Python = $candidate.Source }
        else { throw '没有找到 Python。请由 Agent 配置独立环境后传入 -Python <解释器完整路径>。' }
    }
}
if (Test-Path -LiteralPath $sessionPath) {
    $stateResult = & $Python -X utf8 $studioScript --workspace $workspacePath state
    if ($LASTEXITCODE -eq 0) {
        $existingSession = Get-Content -LiteralPath $sessionPath -Raw | ConvertFrom-Json
        Write-Output $existingSession.url
        return
    }
}
& $Python -X utf8 $studioScript --workspace $workspacePath doctor
if ($LASTEXITCODE -ne 0) { throw '环境体检未通过，请按 doctor 提示先安装依赖。' }
New-Item -ItemType Directory -Force -Path $workspacePath | Out-Null
if ($studioScript.Contains('"') -or $workspacePath.Contains('"')) { throw '路径不能包含双引号。' }
$arguments = '-X utf8 "' + $studioScript + '" --workspace "' + $workspacePath + '" serve --port ' + $Port
Start-Process -FilePath $Python -ArgumentList $arguments -WorkingDirectory $skillRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $workspacePath 'service.log') -RedirectStandardError (Join-Path $workspacePath 'service-error.log')
for ($attempt=0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 200
    if (Test-Path -LiteralPath $sessionPath) {
        & $Python -X utf8 $studioScript --workspace $workspacePath state | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $startedSession = Get-Content -LiteralPath $sessionPath -Raw | ConvertFrom-Json
            Write-Output $startedSession.url
            return
        }
    }
}
throw '工作台未启动，请检查新工作目录中的 service.log 和端口占用。'
