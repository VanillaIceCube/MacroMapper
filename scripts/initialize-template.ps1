[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ApplicationName,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')]
    [string]$ApplicationSlug,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])$')]
    [string]$ProductionHost,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9-]+$')]
    [string]$GitHubOwner
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$compactName = $ApplicationName -replace '[^A-Za-z0-9]', ''

if ([string]::IsNullOrWhiteSpace($compactName)) {
    throw 'ApplicationName must contain at least one letter or number.'
}

$upperSlug = ($ApplicationSlug -replace '-', '_').ToUpperInvariant()
$replacementPairs = @(
    [pscustomobject]@{ Old = 'FullStackTemplate'; New = $compactName },
    [pscustomobject]@{ Old = 'fullstacktemplate'; New = $ApplicationSlug },
    [pscustomobject]@{ Old = 'FULLSTACKTEMPLATE'; New = $upperSlug },
    [pscustomobject]@{ Old = 'app.example.com'; New = $ProductionHost },
    [pscustomobject]@{ Old = 'vanillaicecube'; New = $GitHubOwner.ToLowerInvariant() }
)

$excludedDirectories = @('.git', 'node_modules', '.venv', 'venv', 'dist', 'build', 'coverage')
$textExtensions = @(
    '.css', '.env', '.html', '.js', '.jsx', '.json', '.md', '.ps1', '.py',
    '.svg', '.txt', '.yaml', '.yml'
)
$explicitTextNames = @('.gitignore', 'Dockerfile')

$files = Get-ChildItem -LiteralPath $repoRoot -Recurse -File -Force | Where-Object {
    $relativePath = $_.FullName.Substring($repoRoot.Length).TrimStart([char[]]@('\', '/'))
    $segments = $relativePath -split '[\\/]'
    $isExcluded = $segments | Where-Object { $excludedDirectories -contains $_ }
    (-not $isExcluded) -and (
        $textExtensions -contains $_.Extension.ToLowerInvariant() -or
        $explicitTextNames -contains $_.Name -or
        $_.Name.EndsWith('.env.example')
    )
}

foreach ($file in $files) {
    $content = [System.IO.File]::ReadAllText($file.FullName)
    $updated = $content
    foreach ($pair in $replacementPairs) {
        $updated = $updated.Replace($pair.Old, $pair.New)
    }

    if ($updated -ne $content -and $PSCmdlet.ShouldProcess($file.FullName, 'Apply template branding')) {
        [System.IO.File]::WriteAllText(
            $file.FullName,
            $updated,
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

$renames = @(
    @{
        Source = Join-Path $repoRoot 'frontend/public/fullstacktemplate-mark.svg'
        Target = Join-Path $repoRoot "frontend/public/$ApplicationSlug-mark.svg"
    },
    @{
        Source = Join-Path $repoRoot 'frontend/src/__tests__/fullStackTemplateThemeStyles.test.js'
        Target = Join-Path $repoRoot "frontend/src/__tests__/${compactName}ThemeStyles.test.js"
    }
)

foreach ($rename in $renames) {
    if (
        (Test-Path -LiteralPath $rename.Source) -and
        $rename.Source -ne $rename.Target -and
        $PSCmdlet.ShouldProcess($rename.Source, "Rename to $($rename.Target)")
    ) {
        Move-Item -LiteralPath $rename.Source -Destination $rename.Target
    }
}

Write-Output "Template configured for $ApplicationName."
Write-Output "Local URL: https://$ApplicationSlug.localhost"
Write-Output "Production URL: https://$ProductionHost"
Write-Output 'Review git diff, replace the starter SVG, and follow README.md before opening the first PR.'
