param(
    [string]$Upstream = 'C:\Users\n7210\PycharmProjects\PythonProject\bert-stable-fine-tuning',
    [string]$Config = 'configs/rte-pilot-original.yaml',
    [string]$Attempt = ('pilot-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.runtime\python38\python.exe'
$launcher = Join-Path $PSScriptRoot 'run_pilot.py'
$configPath = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $projectRoot $Config }
foreach ($path in @($pythonPath, $launcher, $configPath, (Join-Path $Upstream 'src\transformers\__init__.py'))) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing prerequisite: $path" }
}
$resultRoot = Join-Path $projectRoot 'results\pilot'
New-Item -ItemType Directory -Path $resultRoot -Force | Out-Null
$stdout = Join-Path $resultRoot ($Attempt + '.stdout.log')
$stderr = Join-Path $resultRoot ($Attempt + '.stderr.log')
$arguments = @('-u', ('"' + $launcher + '"'), '--upstream', ('"' + $Upstream + '"'), '--config', ('"' + $configPath + '"'), '--seed', '0', '--attempt', $Attempt)
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$record = [pscustomobject]@{
    pid = $process.Id
    attempt = $Attempt
    config = $configPath
    stdout = $stdout
    stderr = $stderr
    started_at = (Get-Date -Format o)
}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultRoot 'last-launch.json') -Encoding UTF8
$record | ConvertTo-Json
