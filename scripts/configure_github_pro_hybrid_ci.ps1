[CmdletBinding()]
param(
    [switch]$ApplyRepositorySettings,
    [switch]$CutoverRuleset,
    [switch]$Verify,
    [string]$Repository = "MishaGameHacking/omni-cio-gateway",
    [int]$RulesetId = 20519289,
    [int]$RetentionDays = 7
)

$ErrorActionPreference = "Stop"
$ApiVersion = "2026-03-10"
$RequiredAuthoritativeContext = "V10 authoritative merge gate"
$ExpectedOwner = "MishaGameHacking"
$ExpectedRepo = "omni-cio-gateway"

function Invoke-GhJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "PUT")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body
    )

    $args = @(
        "api",
        "--method", $Method,
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: $ApiVersion",
        $Path
    )

    if ($null -eq $Body) {
        return (& gh @args | ConvertFrom-Json)
    }

    $json = $Body | ConvertTo-Json -Depth 100 -Compress
    return ($json | & gh @args --input -)
}

function Assert-OwnerSession {
    $status = (& gh auth status 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated. Run: gh auth login -h github.com -p https -w"
    }
    if ($status -notmatch "account\s+$ExpectedOwner") {
        throw "Active GitHub CLI account must be $ExpectedOwner. Current auth output:`n$status"
    }

    $repo = Invoke-GhJson -Method GET -Path "repos/$Repository"
    if ($repo.owner.login -ne $ExpectedOwner -or $repo.name -ne $ExpectedRepo) {
        throw "Repository identity mismatch: $($repo.full_name)"
    }
    if (-not $repo.private) {
        throw "Repository must remain private."
    }
}

function Get-RunnerState {
    $runners = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/runners"
    $runner = $runners.runners | Where-Object {
        $_.name -eq "omni-cio-ci" -and
        ($_.labels.name -contains "self-hosted") -and
        ($_.labels.name -contains "Windows") -and
        ($_.labels.name -contains "X64") -and
        ($_.labels.name -contains "omni-cio-ci")
    } | Select-Object -First 1

    if ($null -eq $runner) {
        throw "Required self-hosted runner omni-cio-ci with Windows/X64/omni-cio-ci labels was not found."
    }
    return $runner
}

function Get-Ruleset {
    return Invoke-GhJson -Method GET -Path "repos/$Repository/rulesets/$RulesetId"
}

function Assert-RulesetInvariant {
    param([Parameter(Mandatory = $true)]$Ruleset)

    if ($Ruleset.name -ne "Protect main") { throw "Unexpected ruleset name: $($Ruleset.name)" }
    if ($Ruleset.target -ne "branch") { throw "Ruleset target must remain branch." }
    if ($Ruleset.enforcement -ne "active") { throw "Ruleset enforcement must remain active." }
    if ($Ruleset.bypass_actors.Count -ne 0) { throw "Ruleset bypass list must remain empty." }
    if (@($Ruleset.conditions.ref_name.include) -notcontains "refs/heads/main") {
        throw "Ruleset must target refs/heads/main."
    }
    if (@($Ruleset.conditions.ref_name.exclude).Count -ne 0) {
        throw "Ruleset must not exclude target branches."
    }

    $types = @($Ruleset.rules.type)
    foreach ($required in @("deletion", "non_fast_forward", "pull_request", "required_status_checks")) {
        if ($types -notcontains $required) { throw "Ruleset is missing mandatory rule: $required" }
    }

    $pr = $Ruleset.rules | Where-Object type -eq "pull_request" | Select-Object -First 1
    if ($pr.parameters.required_approving_review_count -ne 0) { throw "Unexpected approval count." }
    if (-not $pr.parameters.required_review_thread_resolution) { throw "Conversation resolution must remain required." }
    if (@($pr.parameters.allowed_merge_methods).Count -ne 1 -or $pr.parameters.allowed_merge_methods[0] -ne "squash") {
        throw "Squash must remain the only allowed merge method."
    }

    $status = $Ruleset.rules | Where-Object type -eq "required_status_checks" | Select-Object -First 1
    if (-not $status.parameters.strict_required_status_checks_policy) { throw "Strict/up-to-date status policy must remain enabled." }
    if ($status.parameters.do_not_enforce_on_create) { throw "Status checks must remain enforced on branch updates." }
}

function Assert-AuthoritativeCheckGreen {
    $pr = Invoke-GhJson -Method GET -Path "repos/$Repository/pulls/242"
    if ($pr.state -ne "open") { throw "Infrastructure PR #242 must be open during cutover verification." }
    $head = $pr.head.sha
    $checks = Invoke-GhJson -Method GET -Path "repos/$Repository/commits/$head/check-runs"

    $required = @(
        "Fast policy and source contracts",
        "Fast frontend type lint unit build",
        "Python 3.14.6 V10 baseline",
        "Node 24.18.0 / React-Vite-TypeScript baseline",
        "Windows runner smoke test",
        $RequiredAuthoritativeContext
    )

    foreach ($name in $required) {
        $matching = @($checks.check_runs | Where-Object name -eq $name | Sort-Object completed_at -Descending)
        if ($matching.Count -eq 0) { throw "Required exact-head check is missing: $name (head $head)" }
        if ($matching[0].status -ne "completed" -or $matching[0].conclusion -ne "success") {
            throw "Required exact-head check is not green: $name => $($matching[0].status)/$($matching[0].conclusion)"
        }
    }
    return $head
}

Assert-OwnerSession
$runner = Get-RunnerState
Write-Host "Runner:" $runner.name $runner.status "busy=" $runner.busy

if ($ApplyRepositorySettings) {
    if ($RetentionDays -lt 1 -or $RetentionDays -gt 400) {
        throw "RetentionDays must be between 1 and 400 for a private repository."
    }

    Invoke-GhJson -Method PUT -Path "repos/$Repository/actions/permissions" -Body @{
        enabled = $true
        allowed_actions = "all"
        sha_pinning_required = $true
    } | Out-Null

    Invoke-GhJson -Method PUT -Path "repos/$Repository/actions/permissions/workflow" -Body @{
        default_workflow_permissions = "read"
        can_approve_pull_request_reviews = $false
    } | Out-Null

    Invoke-GhJson -Method PUT -Path "repos/$Repository/actions/permissions/artifact-and-log-retention" -Body @{
        days = $RetentionDays
    } | Out-Null

    Write-Host "Applied repository Actions policy: enabled, full-SHA pinning, read-only default GITHUB_TOKEN, PR approvals disabled, retention=$RetentionDays days."
}

if ($CutoverRuleset) {
    $head = Assert-AuthoritativeCheckGreen
    $ruleset = Get-Ruleset
    Assert-RulesetInvariant -Ruleset $ruleset

    $statusRule = $ruleset.rules | Where-Object type -eq "required_status_checks" | Select-Object -First 1
    $integrationId = 15368
    $authoritativeExisting = @($statusRule.parameters.required_status_checks | Where-Object context -eq $RequiredAuthoritativeContext)
    if ($authoritativeExisting.Count -gt 0 -and $authoritativeExisting[0].integration_id) {
        $integrationId = [int]$authoritativeExisting[0].integration_id
    }

    $statusRule.parameters.required_status_checks = @(
        [pscustomobject]@{
            context = $RequiredAuthoritativeContext
            integration_id = $integrationId
        }
    )

    $body = [ordered]@{
        name = $ruleset.name
        target = $ruleset.target
        enforcement = $ruleset.enforcement
        bypass_actors = @()
        conditions = $ruleset.conditions
        rules = $ruleset.rules
    }

    Invoke-GhJson -Method PUT -Path "repos/$Repository/rulesets/$RulesetId" -Body $body | Out-Null
    Write-Host "Cut over Protect main to authoritative context on exact PR head $head."
}

if ($Verify -or (-not $ApplyRepositorySettings -and -not $CutoverRuleset)) {
    $workflowPolicy = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/permissions/workflow"
    $retention = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/permissions/artifact-and-log-retention"
    $ruleset = Get-Ruleset
    Assert-RulesetInvariant -Ruleset $ruleset

    Write-Host "Default workflow permissions:" $workflowPolicy.default_workflow_permissions
    Write-Host "Actions may approve PRs:" $workflowPolicy.can_approve_pull_request_reviews
    Write-Host "Artifact/log retention days:" $retention.days
    Write-Host "Protect main required contexts:"
    ($ruleset.rules | Where-Object type -eq "required_status_checks").parameters.required_status_checks |
        ForEach-Object { Write-Host " -" $_.context }
}
