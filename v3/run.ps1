param([ValidateSet('prepare','run','analyze','publish','judge','judge2')][string]$Action='analyze',[switch]$DirectNetwork)
$ErrorActionPreference='Stop'
$projectRoot=Join-Path $PSScriptRoot '../customer-support'
$credentialPath=Join-Path $projectRoot '.credentials.local.json'
try {
    if($Action -in @('run','publish','judge','judge2')) {
        $tokens=$null; $parseErrors=$null
        $tree=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $projectRoot 'credentials.ps1'),[ref]$tokens,[ref]$parseErrors)
        if($parseErrors.Count){throw 'Credential loader parse failed.'}
        $loader=$tree.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Read-SavedCredentials'},$true)
        if(-not $loader){throw 'Saved credential loader missing.'}
        . ([scriptblock]::Create($loader.Extent.Text))
        Read-SavedCredentials
    }
    if($Action -eq 'judge2') {
        & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B -X utf8 (Join-Path $PSScriptRoot 'judge_v2.py')
    } elseif($Action -eq 'judge') {
        & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B -X utf8 (Join-Path $PSScriptRoot 'judge_v3.py')
    } elseif($Action -eq 'publish') {
        & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B -X utf8 (Join-Path $PSScriptRoot 'publish_langsmith.py')
    } else {
        $extra=@();if($DirectNetwork){$extra+= '--direct-network'}
        & (Join-Path $projectRoot '.venv/Scripts/python.exe') -B -X utf8 (Join-Path $PSScriptRoot 'experiment.py') $Action @extra
    }
    if($LASTEXITCODE -ne 0){throw 'V3 action failed. Saved outputs remain available for resume.'}
} finally {
    [Environment]::SetEnvironmentVariable('OPENAI_API_KEY',$null,'Process')
    [Environment]::SetEnvironmentVariable('LANGSMITH_API_KEY',$null,'Process')
}
