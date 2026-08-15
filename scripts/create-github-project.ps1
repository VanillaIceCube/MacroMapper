[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Owner,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Repository,

    [string]$ProjectTitle = $Repository,

    [string]$SourceProjectOwner = 'VanillaIceCube',

    [ValidateRange(1, [int]::MaxValue)]
    [int]$SourceProjectNumber = 8
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI (gh) is required. Install it and run gh auth login first.'
}

gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'GitHub CLI is not authenticated. Run gh auth login, then gh auth refresh -s project.'
}

function Invoke-Gh {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & gh @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI failed: gh $($Arguments -join ' ')"
    }
    return $output
}

function Get-Project {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectOwner,

        [Parameter(Mandatory = $true)]
        [int]$ProjectNumber
    )

    $rawProject = Invoke-Gh -Arguments @(
        'project', 'view', "$ProjectNumber",
        '--owner', $ProjectOwner,
        '--format', 'json'
    )
    return ($rawProject | ConvertFrom-Json)
}

function Get-ProjectFieldSignature {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectOwner,

        [Parameter(Mandatory = $true)]
        [int]$ProjectNumber
    )

    $rawFields = Invoke-Gh -Arguments @(
        'project', 'field-list', "$ProjectNumber",
        '--owner', $ProjectOwner,
        '--limit', '100',
        '--format', 'json'
    )
    $fieldResponse = $rawFields | ConvertFrom-Json

    $fields = foreach ($field in ($fieldResponse.fields | Sort-Object -Property name)) {
        [ordered]@{
            name = $field.name
            type = $field.type
            options = @($field.options | ForEach-Object { $_.name })
        }
    }

    return ($fields | ConvertTo-Json -Depth 10 -Compress)
}

function Get-ProjectLayout {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectId
    )

    $query = @'
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      views(first: 50) {
        nodes {
          name
          layout
          filter
          fields(first: 50) {
            nodes {
              __typename
              ... on ProjectV2Field { name }
              ... on ProjectV2SingleSelectField { name }
              ... on ProjectV2IterationField { name }
            }
          }
          groupByFields(first: 20) {
            nodes {
              __typename
              ... on ProjectV2Field { name }
              ... on ProjectV2SingleSelectField { name }
              ... on ProjectV2IterationField { name }
            }
          }
          sortByFields(first: 20) {
            nodes {
              direction
              field {
                __typename
                ... on ProjectV2Field { name }
                ... on ProjectV2SingleSelectField { name }
                ... on ProjectV2IterationField { name }
              }
            }
          }
          verticalGroupByFields(first: 20) {
            nodes {
              __typename
              ... on ProjectV2Field { name }
              ... on ProjectV2SingleSelectField { name }
              ... on ProjectV2IterationField { name }
            }
          }
        }
      }
      workflows(first: 50) {
        nodes {
          name
          enabled
        }
      }
    }
  }
}
'@

    $rawLayout = Invoke-Gh -Arguments @(
        'api', 'graphql',
        '-F', "projectId=$ProjectId",
        '-f', "query=$query"
    )
    $layout = ($rawLayout | ConvertFrom-Json).data.node

    if (-not $layout) {
        throw "Could not read Project layout for $ProjectId."
    }

    return $layout
}

function Get-ViewSignature {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Layout
    )

    $views = foreach ($view in ($Layout.views.nodes | Sort-Object -Property name)) {
        $sortFields = foreach ($sortField in $view.sortByFields.nodes) {
            [ordered]@{
                direction = $sortField.direction
                field = $sortField.field.name
            }
        }

        [ordered]@{
            name = $view.name
            layout = $view.layout
            filter = $view.filter
            fields = @($view.fields.nodes.name | Sort-Object)
            groupByFields = @($view.groupByFields.nodes.name | Sort-Object)
            sortByFields = @($sortFields)
            verticalGroupByFields = @(
                $view.verticalGroupByFields.nodes.name | Sort-Object
            )
        }
    }

    return ($views | ConvertTo-Json -Depth 20 -Compress)
}

function Get-CopiedWorkflowSignature {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Layout
    )

    $workflows = @(
        $Layout.workflows.nodes |
            Where-Object { $_.name -ne 'Auto-add to project' } |
            Sort-Object -Property name
    )
    return ($workflows | ConvertTo-Json -Depth 10 -Compress)
}

function Test-ProjectLinkedRepository {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectId,

        [Parameter(Mandatory = $true)]
        [string]$RepositoryWithOwner
    )

    $query = @'
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      repositories(first: 100) {
        nodes { nameWithOwner }
      }
    }
  }
}
'@

    $rawResponse = Invoke-Gh -Arguments @(
        'api', 'graphql',
        '-F', "projectId=$ProjectId",
        '-f', "query=$query"
    )
    $repositories = ($rawResponse | ConvertFrom-Json).data.node.repositories.nodes
    return $RepositoryWithOwner -in $repositories.nameWithOwner
}

$sourceProject = Get-Project `
    -ProjectOwner $SourceProjectOwner `
    -ProjectNumber $SourceProjectNumber
$sourceFields = Get-ProjectFieldSignature `
    -ProjectOwner $SourceProjectOwner `
    -ProjectNumber $SourceProjectNumber
$sourceLayout = Get-ProjectLayout -ProjectId $sourceProject.id

$existingProjectsRaw = Invoke-Gh -Arguments @(
    'project', 'list',
    '--owner', $Owner,
    '--limit', '100',
    '--format', 'json'
)
$existingProjects = ($existingProjectsRaw | ConvertFrom-Json).projects
$matchingProjects = @(
    $existingProjects | Where-Object { $_.title -eq $ProjectTitle }
)

if ($matchingProjects.Count -gt 1) {
    $matches = $matchingProjects.url -join ', '
    throw "Multiple Projects named '$ProjectTitle' exist: $matches. No duplicate was created."
}

$project = $null
$reuseExistingProject = $false
if ($matchingProjects.Count -eq 1) {
    $project = $matchingProjects[0]
    if (
        -not (
            Test-ProjectLinkedRepository `
                -ProjectId $project.id `
                -RepositoryWithOwner "$Owner/$Repository"
        )
    ) {
        throw "Project '$ProjectTitle' already exists but is not linked to $Owner/$($Repository): $($project.url)"
    }
    $reuseExistingProject = $true
}

$target = "$Owner/$Repository Project '$ProjectTitle'"
$action = if ($reuseExistingProject) {
    'Verify and finish the existing linked Project'
} else {
    "Copy $SourceProjectOwner Project $SourceProjectNumber"
}
if (-not $PSCmdlet.ShouldProcess($target, $action)) {
    if ($reuseExistingProject) {
        Write-Output "Would reuse $($project.url)."
    } else {
        Write-Output "Would copy $($sourceProject.url) to $Owner as '$ProjectTitle'."
        Write-Output "Would link the copied Project to $Owner/$Repository."
    }
    Write-Output 'Would verify fields, views, and configured workflows.'
    Write-Output 'Would set repository variable SECURITY_ALERTS_PROJECT_ID.'
    return
}

if (-not $reuseExistingProject) {
    $copyRaw = Invoke-Gh -Arguments @(
        'project', 'copy', "$SourceProjectNumber",
        '--source-owner', $SourceProjectOwner,
        '--target-owner', $Owner,
        '--title', $ProjectTitle,
        '--format', 'json'
    )
    $project = $copyRaw | ConvertFrom-Json

    if (-not $project.id -or -not $project.number -or -not $project.url) {
        throw 'GitHub did not return the copied Project ID, number, and URL.'
    }
}

$description = "$Repository is a full-stack React and Django application. This Project tracks features, bugs, UX, backend work, deployment, security, and CI/CD."
$readme = @"
This board is used to plan and track work for $Repository.

Issues here cover product features, bugs, UI improvements, backend changes, refactors, security, deployment, and long-term ideas. The goal is to keep development organized while the application grows from the reusable FullStackTemplate foundation.
"@

Invoke-Gh -Arguments @(
    'project', 'edit', "$($project.number)",
    '--owner', $Owner,
    '--title', $ProjectTitle,
    '--description', $description,
    '--readme', $readme,
    '--visibility', 'PUBLIC'
) | Out-Null

if (-not $reuseExistingProject) {
    Invoke-Gh -Arguments @(
        'project', 'link', "$($project.number)",
        '--owner', $Owner,
        '--repo', "$Owner/$Repository"
    ) | Out-Null
}

$targetFields = Get-ProjectFieldSignature `
    -ProjectOwner $Owner `
    -ProjectNumber $project.number
$targetLayout = Get-ProjectLayout -ProjectId $project.id

if ($targetFields -cne $sourceFields) {
    throw "Copied Project fields do not match $($sourceProject.title)."
}

if ((Get-ViewSignature -Layout $targetLayout) -cne (Get-ViewSignature -Layout $sourceLayout)) {
    throw "Copied Project views do not match $($sourceProject.title)."
}

if (
    (Get-CopiedWorkflowSignature -Layout $targetLayout) -cne
    (Get-CopiedWorkflowSignature -Layout $sourceLayout)
) {
    throw "Copied Project workflows do not match $($sourceProject.title)."
}

Invoke-Gh -Arguments @(
    'variable', 'set', 'SECURITY_ALERTS_PROJECT_ID',
    '--repo', "$Owner/$Repository",
    '--body', $project.id
) | Out-Null

if ($reuseExistingProject) {
    Write-Output "Reused existing linked Project $($project.url)"
} else {
    Write-Output "Created and linked $($project.url)"
}
Write-Output "Verified fields, views, and copied workflows against $($sourceProject.url)"
Write-Output 'Set repository variable SECURITY_ALERTS_PROJECT_ID.'
Write-Output "GitHub does not copy the repository-scoped 'Auto-add to project' workflow; configure it for the target repository as documented in docs/GITHUB_SETUP.md."
