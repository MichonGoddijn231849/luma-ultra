param(
    [Parameter(Mandatory = $true)]
    [string]$Repository,
    [string]$Visibility = "public",
    [switch]$SkipReleaseTag
)

$ErrorActionPreference = "Stop"

function Ensure-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required but was not found on PATH."
    }
}

Ensure-Command git
Ensure-Command gh

$repoRoot = $PSScriptRoot
$version = (Get-Content (Join-Path $repoRoot "VERSION") -Raw).Trim()

$null = & gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not logged in. Run 'gh auth login' first."
}

if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
    & git -C $repoRoot init -b main
}

& git -C $repoRoot add .

$status = & git -C $repoRoot status --porcelain
if ($status) {
    & git -C $repoRoot commit -m "Initial release setup"
}

$remotes = & git -C $repoRoot remote
$remote = if ($remotes -contains "origin") {
    & git -C $repoRoot remote get-url origin
} else {
    $null
}
if (-not $remote) {
    & gh repo create $Repository "--$Visibility" --source $repoRoot --remote origin --push
} else {
    & git -C $repoRoot push -u origin main
}

if (-not $SkipReleaseTag) {
    $tag = "v$version"
    $existingTag = & git -C $repoRoot tag --list $tag
    if (-not $existingTag) {
        & git -C $repoRoot tag $tag
    }

    & git -C $repoRoot push origin $tag
}
