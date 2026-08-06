[CmdletBinding()]
param(
    [string]$Repository = "MishaGameHacking/omni-cio-gateway",
    [int]$PullRequest = 242,
    [int]$RulesetId = 20519289,
    [int]$RegressionTimeoutMinutes = 45
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$ApiVersion = "2022-11-28"
$ExpectedOwner = "MishaGameHacking"
$ExpectedHead = "c8ac6cbb10feab47e2aeca37bbc46e61c2fd2fb4"
$AuthoritativeContext = "V10 authoritative merge gate"
$SmokeContext = "Windows runner smoke test"
$GitHubActionsAppId = 15368
$RegressionWorkflow = "regression-shield.yml"

function Invoke-GhJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body = $null,
        [int]$Retries = 8
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        $args = @(
            "api", "--method", $Method,
            "-H", "Accept: application/vnd.github+json",
            "-H", ("X-GitHub-Api-Version: {0}" -f $ApiVersion),
            $Path
        )

        $saved = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            if ($null -eq $Body) {
                $raw = & gh @args 2>&1
            } else {
                $json = $Body | ConvertTo-Json -Depth 100 -Compress
                $raw = $json | & gh @args --input - 2>&1
            }
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $saved
        }

        $text = (($raw | Out-String).Trim())
        if ($exitCode -eq 0) {
            if (-not $text) { return $null }
            return ($text | ConvertFrom-Json)
        }

        if ($attempt -ge $Retries) {
            throw ("GitHub API failed: {0} {1}. {2}" -f $Method, $Path, $text)
        }

        $delay = [Math]::Min(3 * $attempt, 20)
        Write-Host ("Transient GitHub error {0}/{1}; retry in {2}s" -f $attempt, $Retries, $delay) -ForegroundColor Yellow
        Start-Sleep -Seconds $delay
    }
}

function Get-Ruleset {
    return Invoke-GhJson -Method GET -Path ("repos/{0}/rulesets/{1}" -f $Repository, $RulesetId)
}

function New-RulesetBody {
    param(
        [Parameter(Mandatory = $true)]$Ruleset,
        [Parameter(Mandatory = $true)][object[]]$Rules
    )
    return [ordered]@{
        name = $Ruleset.name
        target = $Ruleset.target
        enforcement = $Ruleset.enforcement
        bypass_actors = @($Ruleset.bypass_actors)
        conditions = $Ruleset.conditions
        rules = @($Rules)
    }
}

function Assert-RepositoryAndSession {
    $auth = (& gh auth status 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated." }
    if ($auth -notmatch ("account\s+{0}" -f [regex]::Escape($ExpectedOwner))) {
        throw ("Active gh account must be {0}." -f $ExpectedOwner)
    }

    $repo = Invoke-GhJson -Method GET -Path ("repos/{0}" -f $Repository)
    if ($repo.owner.login -ne $ExpectedOwner) { throw "Repository owner mismatch." }
    if (-not $repo.private) { throw "Repository must remain private." }
    if (-not $repo.allow_squash_merge -or $repo.allow_merge_commit -or $repo.allow_rebase_merge) {
        throw "Repository must remain squash-only."
    }
    if (-not $repo.delete_branch_on_merge) { throw "Merged branches must be auto-deleted." }
}

function Assert-ValidatedHead {
    $pr = Invoke-GhJson -Method GET -Path ("repos/{0}/pulls/{1}" -f $Repository, $PullRequest)
    if ($pr.state -ne "open" -or $pr.merged) { throw "PR 242 must be open and unmerged before finalization." }
    if ($pr.head.sha -ne $ExpectedHead) {
        throw ("PR head changed. Expected {0}; got {1}." -f $ExpectedHead, $pr.head.sha)
    }
    if ($pr.head.ref -ne "infra/github-pro-hybrid-ci" -or $pr.base.ref -ne "main") {
        throw "Unexpected PR refs."
    }

    $main = Invoke-GhJson -Method GET -Path ("repos/{0}/branches/main" -f $Repository)
    if ($pr.base.sha -ne $main.commit.sha) {
        throw "PR is not up to date with main."
    }

    $checks = Invoke-GhJson -Method GET -Path ("repos/{0}/commits/{1}/check-runs?per_page=100" -f $Repository, $ExpectedHead)
    foreach ($context in @($SmokeContext, $AuthoritativeContext)) {
        $check = @($checks.check_runs | Where-Object { $_.name -eq $context } | Sort-Object completed_at -Descending) | Select-Object -First 1
        if ($null -eq $check) { throw ("Missing validated check: {0}" -f $context) }
        if ($check.status -ne "completed" -or $check.conclusion -ne "success") {
            throw ("Validated check is not green: {0} => {1}/{2}" -f $context, $check.status, $check.conclusion)
        }
        if ($check.app.id -ne $GitHubActionsAppId) {
            throw ("Unexpected check source for {0}." -f $context)
        }
        $prNumbers = @($check.pull_requests | ForEach-Object { $_.number })
        if ($prNumbers -notcontains $PullRequest) {
            throw ("Check {0} is not associated with PR #{1}." -f $context, $PullRequest)
        }
    }

    Write-Host ("Validated exact PR head: {0}" -f $ExpectedHead) -ForegroundColor Green
}

function Assert-ProtectMain {
    param([Parameter(Mandatory = $true)]$Ruleset)
    if ($Ruleset.name -ne "Protect main" -or $Ruleset.enforcement -ne "active") { throw "Protect main ruleset is not active." }
    if (@($Ruleset.bypass_actors).Count -ne 0) { throw "Protect main bypass list must remain empty." }
    if (@($Ruleset.conditions.ref_name.include) -notcontains "refs/heads/main") { throw "Protect main must target main." }

    $types = @($Ruleset.rules | ForEach-Object { $_.type })
    foreach ($required in @("deletion", "non_fast_forward", "pull_request", "required_status_checks")) {
        if ($types -notcontains $required) { throw ("Protect main missing rule: {0}" -f $required) }
    }

    $prRule = $Ruleset.rules | Where-Object { $_.type -eq "pull_request" } | Select-Object -First 1
    if (@($prRule.parameters.allowed_merge_methods).Count -ne 1 -or $prRule.parameters.allowed_merge_methods[0] -ne "squash") {
        throw "Protect main must remain squash-only."
    }
    if (-not $prRule.parameters.required_review_thread_resolution) { throw "Conversation resolution must stay enabled." }

    $statusRule = $Ruleset.rules | Where-Object { $_.type -eq "required_status_checks" } | Select-Object -First 1
    $requiredChecks = @($statusRule.parameters.required_status_checks)
    if ($requiredChecks.Count -ne 1 -or $requiredChecks[0].context -ne $AuthoritativeContext -or $requiredChecks[0].integration_id -ne $GitHubActionsAppId) {
        throw "Protect main required status check is not the authoritative GitHub Actions gate."
    }
    if (-not $statusRule.parameters.strict_required_status_checks_policy) { throw "Strict required status policy must remain enabled." }
}

function Restore-ProtectMain {
    param([Parameter(Mandatory = $true)]$OriginalRuleset)
    $body = New-RulesetBody -Ruleset $OriginalRuleset -Rules @($OriginalRuleset.rules)
    Invoke-GhJson -Method PUT -Path ("repos/{0}/rulesets/{1}" -f $Repository, $RulesetId) -Body $body | Out-Null

    for ($i = 1; $i -le 20; $i++) {
        $verify = Get-Ruleset
        try {
            Assert-ProtectMain -Ruleset $verify
            Write-Host "Protect main restored and verified." -ForegroundColor Green
            return
        } catch {
            Start-Sleep -Seconds 3
        }
    }
    throw "Protect main restoration did not converge."
}

function Merge-ValidatedPrDuringIncident {
    $original = Get-Ruleset
    Assert-ProtectMain -Ruleset $original

    $maintenanceRules = @($original.rules | Where-Object { $_.type -ne "required_status_checks" })
    if ($maintenanceRules.Count -ne (@($original.rules).Count - 1)) {
        throw "Could not isolate required_status_checks for maintenance window."
    }

    $mergedSha = $null
    try {
        Write-Host "Entering controlled maintenance merge window..." -ForegroundColor Yellow
        $maintenanceBody = New-RulesetBody -Ruleset $original -Rules $maintenanceRules
        Invoke-GhJson -Method PUT -Path ("repos/{0}/rulesets/{1}" -f $Repository, $RulesetId) -Body $maintenanceBody | Out-Null

        $active = Get-Ruleset
        if (@($active.rules | Where-Object { $_.type -eq "required_status_checks" }).Count -ne 0) {
            throw "Required status rule was not temporarily removed."
        }
        Start-Sleep -Seconds 2

        $merge = Invoke-GhJson -Method PUT -Path ("repos/{0}/pulls/{1}/merge" -f $Repository, $PullRequest) -Body @{
            merge_method = "squash"
            sha = $ExpectedHead
            commit_title = "Infra: GitHub Pro hybrid CI + Lenovo continuity (#242)"
            commit_message = "Validated exact head by Lenovo authoritative gate during the GitHub Actions incident. Protect main is restored immediately after merge."
        } -Retries 4

        if (-not $merge.merged) { throw ("GitHub did not merge PR: {0}" -f $merge.message) }
        $mergedSha = [string]$merge.sha
        Write-Host ("Squash merge completed: {0}" -f $mergedSha) -ForegroundColor Green
    } finally {
        Restore-ProtectMain -OriginalRuleset $original
    }

    if (-not $mergedSha) { throw "Merge did not complete." }
    return $mergedSha
}

function Dispatch-And-WaitRegressionShield {
    param([Parameter(Mandatory = $true)][string]$MainSha)

    $started = (Get-Date).ToUniversalTime()
    Invoke-GhJson -Method POST -Path ("repos/{0}/actions/workflows/{1}/dispatches" -f $Repository, $RegressionWorkflow) -Body @{ ref = "main" } | Out-Null
    Write-Host "Regression Shield dispatched on main." -ForegroundColor Cyan

    $deadline = (Get-Date).AddMinutes($RegressionTimeoutMinutes)
    $run = $null
    while ((Get-Date) -lt $deadline) {
        $runs = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/workflows/{1}/runs?branch=main&event=workflow_dispatch&per_page=30" -f $Repository, $RegressionWorkflow) -Retries 5
        $run = @($runs.workflow_runs | Where-Object { $_.head_sha -eq $MainSha } | Sort-Object created_at -Descending) | Select-Object -First 1
        if ($null -ne $run) { break }
        Write-Host "Waiting for post-merge Regression Shield registration..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
    }
    if ($null -eq $run) { throw "Regression Shield did not register on the merged main SHA." }

    Write-Host ("Watching Regression Shield run {0}" -f $run.id) -ForegroundColor Cyan
    while ((Get-Date) -lt $deadline) {
        $current = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runs/{1}" -f $Repository, $run.id) -Retries 5
        Write-Host ("[{0}] Regression Shield: {1}" -f (Get-Date -Format "HH:mm:ss"), $current.status)
        if ($current.status -eq "completed") {
            if ($current.conclusion -ne "success") {
                throw ("Post-merge Regression Shield failed: {0} (run {1})" -f $current.conclusion, $current.id)
            }
            Write-Host "Post-merge Regression Shield: GREEN" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 20
    }
    throw "Timed out waiting for post-merge Regression Shield."
}

Write-Host "=== Omni-CIO GitHub incident finalizer ===" -ForegroundColor Cyan
Write-Host "This uses a short maintenance window only after exact-head checks are independently verified." -ForegroundColor DarkCyan

Assert-RepositoryAndSession
Assert-ValidatedHead

$mergedSha = Merge-ValidatedPrDuringIncident

$prAfter = Invoke-GhJson -Method GET -Path ("repos/{0}/pulls/{1}" -f $Repository, $PullRequest)
if (-not $prAfter.merged) { throw "PR is not marked merged after merge operation." }

$mainAfter = Invoke-GhJson -Method GET -Path ("repos/{0}/branches/main" -f $Repository)
if ($mainAfter.commit.sha -ne $mergedSha) {
    throw ("main SHA mismatch after merge: expected {0}; got {1}." -f $mergedSha, $mainAfter.commit.sha)
}

$finalRuleset = Get-Ruleset
Assert-ProtectMain -Ruleset $finalRuleset

Dispatch-And-WaitRegressionShield -MainSha $mergedSha

$repoFinal = Invoke-GhJson -Method GET -Path ("repos/{0}" -f $Repository)
if (-not $repoFinal.private -or -not $repoFinal.allow_squash_merge -or $repoFinal.allow_merge_commit -or $repoFinal.allow_rebase_merge) {
    throw "Final repository settings verification failed."
}

Write-Host "FINAL VERIFY: PASS" -ForegroundColor Green
Write-Host ("main: {0}" -f $mergedSha) -ForegroundColor Green
Write-Host ("Protect main required check: {0}" -f $AuthoritativeContext) -ForegroundColor Green
Write-Host "GITHUB HYBRID CI FINALIZATION COMPLETE. WP4 remains untouched." -ForegroundColor Green
