param([ValidateSet('probe','prepare','pilot','full','analyze','verify')][string]$Action='verify')
$ErrorActionPreference='Stop'
$projectRoot=Join-Path $PSScriptRoot '../customer-support'
$env:PYTHONDONTWRITEBYTECODE='1'
# Import only the established loader function, without executing its action dispatcher.
$tokens=$null; $parseErrors=$null
$tree=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $projectRoot 'credentials.ps1'),[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count) { throw 'Credential loader parse failed.' }
$loader=$tree.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Read-SavedCredentials'},$true)
if (-not $loader) { throw 'Established credential loader missing.' }
$credentialPath=Join-Path $projectRoot '.credentials.local.json'
try {
    if ($Action -in @('probe','pilot','full')) {
        . ([scriptblock]::Create($loader.Extent.Text))
        Read-SavedCredentials
    }
    & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B -X utf8 (Join-Path $PSScriptRoot 'judge.py') $Action
    if ($LASTEXITCODE -ne 0) { throw "Judge action failed: $Action" }
} finally {
    [Environment]::SetEnvironmentVariable('OPENAI_API_KEY',$null,'Process')
    [Environment]::SetEnvironmentVariable('LANGSMITH_API_KEY',$null,'Process')
}
