param(
    [ValidateSet('Configure','Check','RunLangSmith','RunBaseline','RunFocused','SyncAnnotations')]
    [string]$Action = 'Configure',
    [string]$DatasetName = '',
    [string]$RunName = ''
)
$ErrorActionPreference = 'Stop'
$credentialPath = Join-Path $PSScriptRoot '.credentials.local.json'

function Read-SavedCredentials {
    if (-not (Test-Path -LiteralPath $credentialPath)) { throw 'Run credentials.ps1 -Action Configure first.' }
    $encrypted = Get-Content -LiteralPath $credentialPath -Raw | ConvertFrom-Json
    foreach ($keyName in @('OPENAI_API_KEY','LANGSMITH_API_KEY')) {
        $secureValue = ConvertTo-SecureString -String $encrypted.$keyName
        $credential = New-Object System.Management.Automation.PSCredential('local', $secureValue)
        [Environment]::SetEnvironmentVariable($keyName, $credential.GetNetworkCredential().Password, 'Process')
    }
}

if ($Action -eq 'Configure') {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'Week 4 P4 API credentials'
    $form.Size = New-Object System.Drawing.Size(570,315)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $label = New-Object System.Windows.Forms.Label
    $label.Text = "Enter keys locally. Both fields are masked.`nSaved keys are encrypted for this Windows account."
    $label.Location = New-Object System.Drawing.Point(20,15)
    $label.Size = New-Object System.Drawing.Size(520,42)
    $form.Controls.Add($label)
    $fields = @{}
    $position = 68
    foreach ($keyName in @('OPENAI_API_KEY','LANGSMITH_API_KEY')) {
        $fieldLabel = New-Object System.Windows.Forms.Label
        $fieldLabel.Text = $keyName
        $fieldLabel.Location = New-Object System.Drawing.Point(20,$position)
        $fieldLabel.Size = New-Object System.Drawing.Size(500,20)
        $form.Controls.Add($fieldLabel)
        $box = New-Object System.Windows.Forms.TextBox
        $box.Location = New-Object System.Drawing.Point(20,($position+22))
        $box.Size = New-Object System.Drawing.Size(510,25)
        $box.UseSystemPasswordChar = $true
        $form.Controls.Add($box)
        $fields[$keyName] = $box
        $position += 65
    }
    $status = New-Object System.Windows.Forms.Label
    $status.Location = New-Object System.Drawing.Point(20,200)
    $status.Size = New-Object System.Drawing.Size(510,22)
    $form.Controls.Add($status)
    $save = New-Object System.Windows.Forms.Button
    $save.Text = 'Save encrypted keys'
    $save.Location = New-Object System.Drawing.Point(320,230)
    $save.Size = New-Object System.Drawing.Size(210,30)
    $form.Controls.Add($save)
    $save.Add_Click({
        try {
            $payload = @{}
            foreach ($keyName in @('OPENAI_API_KEY','LANGSMITH_API_KEY')) {
                $enteredValue = $fields[$keyName].Text.Trim()
                if ([string]::IsNullOrWhiteSpace($enteredValue)) { throw 'Please fill both key fields.' }
                $payload[$keyName] = ConvertFrom-SecureString (ConvertTo-SecureString $enteredValue -AsPlainText -Force)
                $enteredValue = $null
            }
            $payload | ConvertTo-Json | Set-Content -LiteralPath $credentialPath -Encoding UTF8
            $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
            $acl = New-Object System.Security.AccessControl.FileSecurity
            $acl.SetAccessRuleProtection($true,$false)
            $acl.SetOwner($identity.User)
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity.User,'FullControl','Allow')
            $acl.AddAccessRule($rule)
            Set-Acl -LiteralPath $credentialPath -AclObject $acl
            foreach ($box in $fields.Values) { $box.Clear() }
            $payload = $null
            $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
            $form.Close()
        } catch {
            $status.Text = 'Save failed. Check both fields and local folder access.'
        }
    })
    $form.AcceptButton = $save
    $result = $form.ShowDialog()
    $form.Dispose()
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output 'Credentials saved with Windows account encryption.' }
    else { Write-Output 'Setup closed without saving.' }
    exit
}

try {
    Read-SavedCredentials
    if ($Action -eq 'Check') {
        foreach ($keyName in @('OPENAI_API_KEY','LANGSMITH_API_KEY')) {
            if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($keyName,'Process'))) { throw 'A saved credential is empty.' }
        }
        Write-Output 'Both saved keys decrypt successfully. Values are hidden. API validity has not been tested.'
        exit
    }
    $projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $projectPython)) {
        $projectPython = (Get-Command python -ErrorAction Stop).Source
    }
    Push-Location -LiteralPath $PSScriptRoot
    try {
        if ($Action -eq 'SyncAnnotations') {
            & $projectPython sync_annotation_queues.py --apply
        } elseif ($Action -eq 'RunLangSmith') {
            if ([string]::IsNullOrWhiteSpace($DatasetName)) { throw 'Supply a unique -DatasetName.' }
            & $projectPython project.py langsmith --dataset $DatasetName --prefix week4-p4
        } else {
            if ([string]::IsNullOrWhiteSpace($RunName)) { $RunName = Get-Date -Format 'yyyyMMdd-HHmmss' }
            if ($RunName -notmatch '^[A-Za-z0-9_-]+$') { throw 'RunName may contain only letters, numbers, underscores and hyphens.' }
            $version = if ($Action -eq 'RunBaseline') { 'baseline' } else { 'focused' }
            & $projectPython project.py live --version $version --output "live_runs/$version-$RunName.csv"
        }
        if ($LASTEXITCODE -ne 0) { throw 'The evaluation reported an error. Inspect the saved run status.' }
    } finally { Pop-Location }
} finally {
    [Environment]::SetEnvironmentVariable('OPENAI_API_KEY',$null,'Process')
    [Environment]::SetEnvironmentVariable('LANGSMITH_API_KEY',$null,'Process')
}
