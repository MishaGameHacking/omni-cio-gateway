[CmdletBinding()]
param(
    [switch]$ApplyRepositorySettings,
    [switch]$CutoverRuleset,
    [switch]$Verify,
    [switch]$Finalize,
    [string]$Repository = "MishaGameHacking/omni-cio-gateway",
    [int]$RulesetId = 20519289,
    [int]$RetentionDays = 7,
    [int]$WorkflowTimeoutMinutes = 110
)

$ErrorActionPreference = "Stop"
$ApiVersion = "2026-03-10"
$RequiredAuthoritativeContext = "V10 authoritative merge gate"
$ExpectedOwner = "MishaGameHacking"
$ExpectedRepo = "omni-cio-gateway"
$InfrastructurePr = 242
$InfrastructureBranch = "infra/github-pro-hybrid-ci"
$Workflows = @(
    "v10-pr-fast-checks.yml",
    "v10-toolchain-compat.yml",
    "self-hosted-windows-smoke.yml"
)

function Invoke-GhJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH")][string]$Method,
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
        $raw = & gh @args
        if ($LASTEXITCODE -ne 0) { throw "GitHub API request failed: $Method $Path" }
        if (-not $raw) { return $null }
        return ($raw | ConvertFrom-Json)
    }

    $json = $Body | ConvertTo-Json -Depth 100 -Compress
    $raw = $json | & gh @args --input -
    if ($LASTEXITCODE -ne 0) { throw "GitHub API request failed: $Method $Path" }
    if (-not $raw) { return $null }
    return ($raw | ConvertFrom-Json)
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
    if ($runner.status -ne "online") {
        throw "Required self-hosted runner omni-cio-ci is not online."
    }
    return $runner
}

function Get-InfrastructurePr {
    $pr = Invoke-GhJson -Method GET -Path "repos/$Repository/pulls/$InfrastructurePr"
    if ($pr.state -ne "open") { throw "Infrastructure PR #$InfrastructurePr must be open." }
    if ($pr.base.ref -ne "main") { throw "Infrastructure PR must target main." }
    if ($pr.head.ref -ne $InfrastructureBranch) {
        throw "Unexpected infrastructure branch: $($pr.head.ref)"
    }
    return $pr
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
    $pr = Get-InfrastructurePr
    $head = $pr.head.sha
    $checks = Invoke-GhJson -Method GET -Path "repos/$Repository/commits/$head/check-runs?per_page=100"

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

function Start-WorkflowDispatch {
    param(
        [Parameter(Mandatory = $true)][string]$Workflow,
        [Parameter(Mandatory = $true)][string]$Ref
    )
    Invoke-GhJson -Method POST -Path "repos/$Repository/actions/workflows/$Workflow/dispatches" -Body @{ ref = $Ref } | Out-Null
    Write-Host "Dispatched:" $Workflow "on" $Ref
}

function Wait-WorkflowForHead {
    param(
        [Parameter(Mandatory = $true)][string]$Workflow,
        [Parameter(Mandatory = $true)][string]$HeadSha,
        [Parameter(Mandatory = $true)][string]$Branch,
        [int]$TimeoutMinutes = 110
    )

    $encodedBranch = [uri]::EscapeDataString($Branch)
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $run = $null

    while ((Get-Date) -lt $deadline) {
        $runs = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/workflows/$Workflow/runs?branch=$encodedBranch&event=workflow_dispatch&per_page=20"
        $run = @($runs.workflow_runs | Where-Object head_sha -eq $HeadSha | Sort-Object created_at -Descending) | Select-Object -First 1
        if ($null -ne $run) { break }
        Start-Sleep -Seconds 3
    }
    if ($null -eq $run) { throw "Timed out waiting for $Workflow to appear for $HeadSha" }

    Write-Host "Watching:" $Workflow "run" $run.id
    while ((Get-Date) -lt $deadline) {
        $current = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/runs/$($run.id)"
        Write-Host ("[{0}] {1}: {2}" -f (Get-Date -Format "HH:mm:ss"), $Workflow, $current.status)
        if ($current.status -eq "completed") {
            if ($current.conclusion -ne "success") {
                throw "$Workflow failed for exact head $HeadSha: $($current.conclusion) (run $($current.id))"
            }
            Write-Host "GREEN:" $Workflow "run" $current.id
            return $current
        }
        Start-Sleep -Seconds 15
    }
    throw "Timed out waiting for $Workflow to complete for $HeadSha"
}

function Wait-PostMergeRegressionShield {
    param(
        [Parameter(Mandatory = $true)][string]$MainSha,
        [int]$TimeoutMinutes = 90
    )

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $run = $null
    while ((Get-Date) -lt $deadline) {
        $runs = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/workflows/regression-shield.yml/runs?branch=main&event=push&per_page=20"
        $run = @($runs.workflow_runs | Where-Object head_sha -eq $MainSha | Sort-Object created_at -Descending) | Select-Object -First 1
        if ($null -ne $run) { break }
        Start-Sleep -Seconds 3
    }
    if ($null -eq $run) { throw "Post-merge Regression Shield did not appear for main SHA $MainSha" }

    while ((Get-Date) -lt $deadline) {
        $current = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/runs/$($run.id)"
        Write-Host ("[{0}] Regression Shield: {1}" -f (Get-Date -Format "HH:mm:ss"), $current.status)
        if ($current.status -eq "completed") {
            if ($current.conclusion -ne "success") {
                throw "Post-merge Regression Shield failed: $($current.conclusion) (run $($current.id))"
            }
            Write-Host "GREEN: post-merge Regression Shield run" $current.id
            return $current
        }
        Start-Sleep -Seconds 15
    }
    throw "Timed out waiting for post-merge Regression Shield"
}

function Apply-RepositoryPolicy {
    if ($RetentionDays -lt 1 -or $RetentionDays -gt 400) {
        throw "RetentionDays must be between 1 and 400 for a private repository."
    }

    Invoke-GhJson -Method PATCH -Path "repos/$Repository" -Body @{
        allow_squash_merge = $true
        allow_merge_commit = $false
        allow_rebase_merge = $false
        allow_auto_merge = $false
        delete_branch_on_merge = $true
        allow_update_branch = $true
    } | Out-Null

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

    Invoke-GhJson -Method PUT -Path "repos/$Repository/vulnerability-alerts" | Out-Null
    Invoke-GhJson -Method PUT -Path "repos/$Repository/automated-security-fixes" | Out-Null

    Write-Host "Applied repository policy: squash-only, delete merged branches, update-branch enabled, Actions full-SHA pinning, read-only default GITHUB_TOKEN, Actions PR approvals disabled, retention=$RetentionDays days, Dependabot enabled."
}

function Cutover-Ruleset {
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
    return $head
}

function Merge-InfrastructurePr {
    param([Parameter(Mandatory = $true)][string]$ExpectedHead)

    $merge = Invoke-GhJson -Method PUT -Path "repos/$Repository/pulls/$InfrastructurePr/merge" -Body @{
        merge_method = "squash"
        sha = $ExpectedHead
        commit_title = "Infra: GitHub Pro hybrid CI + Lenovo continuity (#$InfrastructurePr)"
        commit_message = "Finalize hosted acceleration with self-hosted authoritative continuity."
    }
    if (-not $merge.merged) { throw "Infrastructure PR merge failed: $($merge.message)" }
    Write-Host "Merged infrastructure PR #$InfrastructurePr:" $merge.sha
    return $merge.sha
}

function Verify-FinalState {
    $repo = Invoke-GhJson -Method GET -Path "repos/$Repository"
    $workflowPolicy = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/permissions/workflow"
    $retention = Invoke-GhJson -Method GET -Path "repos/$Repository/actions/permissions/artifact-and-log-retention"
    $ruleset = Get-Ruleset
    Assert-RulesetInvariant -Ruleset $ruleset

    if (-not $repo.allow_squash_merge -or $repo.allow_merge_commit -or $repo.allow_rebase_merge) {
        throw "Repository merge policy drift detected."
    }
    if (-not $repo.delete_branch_on_merge -or -not $repo.allow_update_branch) {
        throw "Repository branch hygiene policy drift detected."
    }
    if ($workflowPolicy.default_workflow_permissions -ne "read") {
        throw "Default GITHUB_TOKEN must remain read-only."
    }
    if ($workflowPolicy.can_approve_pull_request_reviews) {
        throw "GitHub Actions must not approve pull requests."
    }
    if ($retention.days -ne $RetentionDays) {
        throw "Unexpected artifact/log retention: $($retention.days)"
    }

    $required = @(($ruleset.rules | Where-Object type -eq "required_status_checks").parameters.required_status_checks)
    if ($required.Count -ne 1 -or $required[0].context -ne $RequiredAuthoritativeContext) {
        throw "Protect main must require only the authoritative continuity gate after cutover."
    }

    Write-Host "FINAL VERIFY: PASS"
    Write-Host "Repository:" $repo.full_name
    Write-Host "Main protection:" $ruleset.name $ruleset.enforcement
    Write-Host "Required merge context:" $required[0].context
    Write-Host "Default GITHUB_TOKEN:" $workflowPolicy.default_workflow_permissions
    Write-Host "Artifact/log retention:" $retention.days "days"
}

Assert-OwnerSession
$runner = Get-RunnerState
Write-Host "Runner:" $runner.name $runner.status "busy=" $runner.busy

if ($Finalize) {
    Apply-RepositoryPolicy
    $pr = Get-InfrastructurePr
    $head = $pr.head.sha
    Write-Host "Exact infrastructure head:" $head

    foreach ($workflow in $Workflows) {
        Start-WorkflowDispatch -Workflow $workflow -Ref $InfrastructureBranch
    }
    foreach ($workflow in $Workflows) {
        Wait-WorkflowForHead -Workflow $workflow -HeadSha $head -Branch $InfrastructureBranch -TimeoutMinutes $WorkflowTimeoutMinutes | Out-Null
    }

    $validatedHead = Cutover-Ruleset
    if ($validatedHead -ne $head) {
        throw "PR head moved during finalization. Expected $head, got $validatedHead."
    }

    $mainSha = Merge-InfrastructurePr -ExpectedHead $head
    Wait-PostMergeRegressionShield -MainSha $mainSha -TimeoutMinutes 90 | Out-Null
    Verify-FinalState
    Write-Host "GITHUB HYBRID CI FINALIZATION COMPLETE. WP4 remains untouched."
    exit 0
}

if ($ApplyRepositorySettings) {
    Apply-RepositoryPolicy
}

if ($CutoverRuleset) {
    Cutover-Ruleset | Out-Null
}

if ($Verify -or (-not $ApplyRepositorySettings -and -not $CutoverRuleset)) {
    Verify-FinalState
}
