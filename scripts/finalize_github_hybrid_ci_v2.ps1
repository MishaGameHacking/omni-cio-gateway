[CmdletBinding()]
param(
    [string]$Repository = "MishaGameHacking/omni-cio-gateway",
    [int]$RulesetId = 20519289,
    [int]$InfrastructurePr = 242,
    [string]$InfrastructureBranch = "infra/github-pro-hybrid-ci",
    [int]$RunnerReadyTimeoutMinutes = 15,
    [int]$PreMergeTimeoutMinutes = 55,
    [int]$PostMergeTimeoutMinutes = 70,
    [int]$ApiRetries = 20
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$ApiVersion = "2026-03-10"
$ExpectedOwner = "MishaGameHacking"
$SelfHostedWorkflow = "self-hosted-windows-smoke.yml"
$RegressionWorkflow = "regression-shield.yml"
$SmokeContext = "Windows runner smoke test"
$AuthoritativeContext = "V10 authoritative merge gate"

function Invoke-GhJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body = $null,
        [int]$Retries = $ApiRetries,
        [switch]$NoRetry
    )

    $maxAttempts = if ($NoRetry) { 1 } else { [Math]::Max(1, $Retries) }
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
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

        $detail = ($text -replace "\r?\n", " | ")
        if ($detail.Length -gt 500) { $detail = $detail.Substring(0, 500) }
        if ($attempt -ge $maxAttempts) {
            throw ("GitHub API failed: {0} {1}. {2}" -f $Method, $Path, $detail)
        }

        $delay = [Math]::Min(3 * $attempt, 30)
        Write-Host ("Transient GitHub API/Actions error {0}/{1}; retry in {2}s" -f $attempt, $maxAttempts, $delay) -ForegroundColor Yellow
        if ($detail) { Write-Host ("  {0}" -f $detail) -ForegroundColor DarkYellow }
        Start-Sleep -Seconds $delay
    }
}

function Assert-SessionAndRepository {
    $status = (& gh auth status 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated." }
    if ($status -notmatch ("account\s+{0}" -f [regex]::Escape($ExpectedOwner))) {
        throw ("Active GitHub CLI account must be {0}." -f $ExpectedOwner)
    }

    $repo = Invoke-GhJson -Method GET -Path ("repos/{0}" -f $Repository)
    if ($repo.owner.login -ne $ExpectedOwner) { throw "Repository owner mismatch." }
    if (-not $repo.private) { throw "Repository must remain private." }
    if (-not $repo.allow_squash_merge -or $repo.allow_merge_commit -or $repo.allow_rebase_merge) {
        throw "Repository must remain squash-only."
    }
    if (-not $repo.delete_branch_on_merge -or -not $repo.allow_update_branch) {
        throw "Repository branch hygiene settings drifted."
    }
}

function Wait-RunnerReady {
    $deadline = (Get-Date).AddMinutes($RunnerReadyTimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runners" -f $Repository) -Retries 3
            $runner = @($response.runners | Where-Object {
                $_.name -eq "omni-cio-ci" -and
                $_.status -eq "online" -and
                ($_.labels.name -contains "self-hosted") -and
                ($_.labels.name -contains "Windows") -and
                ($_.labels.name -contains "X64") -and
                ($_.labels.name -contains "omni-cio-ci")
            }) | Select-Object -First 1
            if ($null -ne $runner) {
                Write-Host ("Runner ready: {0}, busy={1}" -f $runner.name, $runner.busy) -ForegroundColor Green
                return $runner
            }
        } catch {
            Write-Host ("Runner status API temporarily unavailable: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
        }
        Write-Host "Waiting for omni-cio-ci to be online..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
    }
    throw "Timed out waiting for online runner omni-cio-ci."
}

function Get-Ruleset {
    return Invoke-GhJson -Method GET -Path ("repos/{0}/rulesets/{1}" -f $Repository, $RulesetId)
}

function Assert-RulesetInvariant {
    param([Parameter(Mandatory = $true)]$Ruleset)
    if ($Ruleset.name -ne "Protect main") { throw "Unexpected ruleset name." }
    if ($Ruleset.target -ne "branch" -or $Ruleset.enforcement -ne "active") { throw "Protect main must remain active." }
    if (@($Ruleset.bypass_actors).Count -ne 0) { throw "Ruleset bypass list must remain empty." }
    if (@($Ruleset.conditions.ref_name.include) -notcontains "refs/heads/main") { throw "Ruleset must target main." }
    if (@($Ruleset.conditions.ref_name.exclude).Count -ne 0) { throw "Ruleset must not exclude branches." }

    $types = @($Ruleset.rules.type)
    foreach ($requiredType in @("deletion", "non_fast_forward", "pull_request", "required_status_checks")) {
        if ($types -notcontains $requiredType) { throw ("Missing mandatory ruleset rule: {0}" -f $requiredType) }
    }

    $prRule = $Ruleset.rules | Where-Object type -eq "pull_request" | Select-Object -First 1
    if ($prRule.parameters.required_approving_review_count -ne 0) { throw "Approval-count policy drifted." }
    if (-not $prRule.parameters.required_review_thread_resolution) { throw "Conversation resolution must remain required." }
    $methods = @($prRule.parameters.allowed_merge_methods)
    if ($methods.Count -ne 1 -or $methods[0] -ne "squash") { throw "Squash must remain the only merge method." }

    $statusRule = $Ruleset.rules | Where-Object type -eq "required_status_checks" | Select-Object -First 1
    if (-not $statusRule.parameters.strict_required_status_checks_policy) { throw "Strict status policy must remain enabled." }
    if ($statusRule.parameters.do_not_enforce_on_create) { throw "Required checks must remain enforced." }
}

function Get-OpenInfrastructurePr {
    $pr = Invoke-GhJson -Method GET -Path ("repos/{0}/pulls/{1}" -f $Repository, $InfrastructurePr)
    if ($pr.merged) { return $pr }
    if ($pr.state -ne "open") { throw ("Infrastructure PR #{0} is not open." -f $InfrastructurePr) }
    if ($pr.draft) { throw "Infrastructure PR must not be draft." }
    if ($pr.head.ref -ne $InfrastructureBranch -or $pr.base.ref -ne "main") { throw "Infrastructure PR refs are unexpected." }

    $main = Invoke-GhJson -Method GET -Path ("repos/{0}/branches/main" -f $Repository)
    if ($pr.base.sha -ne $main.commit.sha) {
        throw ("Infrastructure PR is not up to date with main. PR base={0}; main={1}" -f $pr.base.sha, $main.commit.sha)
    }
    return $pr
}

function Dispatch-Workflow {
    param(
        [Parameter(Mandatory = $true)][string]$Workflow,
        [Parameter(Mandatory = $true)][string]$Ref
    )
    Invoke-GhJson -Method POST -Path ("repos/{0}/actions/workflows/{1}/dispatches" -f $Repository, $Workflow) -Body @{ ref = $Ref } | Out-Null
    Write-Host ("Dispatched: {0} on {1}" -f $Workflow, $Ref) -ForegroundColor Cyan
}

function Show-FailedRunDiagnostics {
    param([Parameter(Mandatory = $true)][long]$RunId)
    try {
        $jobs = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runs/{1}/jobs?per_page=100" -f $Repository, $RunId) -Retries 4
        foreach ($job in @($jobs.jobs | Where-Object conclusion -eq "failure")) {
            Write-Host ("FAILED JOB: {0}" -f $job.name) -ForegroundColor Red
            foreach ($step in @($job.steps | Where-Object conclusion -eq "failure")) {
                Write-Host ("  failed step: {0}" -f $step.name) -ForegroundColor Red
            }
        }
        Write-Host "Last failed-job log output:" -ForegroundColor Yellow
        $saved = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try { & gh run view $RunId --repo $Repository --log-failed 2>&1 | Select-Object -Last 80 | ForEach-Object { Write-Host $_ } } finally { $ErrorActionPreference = $saved }
    } catch {
        Write-Host ("Could not render additional diagnostics: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }
}

function Wait-WorkflowExactHead {
    param(
        [Parameter(Mandatory = $true)][string]$Workflow,
        [Parameter(Mandatory = $true)][string]$Branch,
        [Parameter(Mandatory = $true)][string]$HeadSha,
        [Parameter(Mandatory = $true)][int]$TimeoutMinutes
    )

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $encodedBranch = [uri]::EscapeDataString($Branch)
    $run = $null

    while ((Get-Date) -lt $deadline) {
        $runs = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/workflows/{1}/runs?branch={2}&event=workflow_dispatch&per_page=50" -f $Repository, $Workflow, $encodedBranch) -Retries 5
        $run = @($runs.workflow_runs | Where-Object head_sha -eq $HeadSha | Sort-Object created_at -Descending) | Select-Object -First 1
        if ($null -ne $run) { break }
        Write-Host ("Waiting for exact-head run registration: {0}" -f $Workflow)
        Start-Sleep -Seconds 10
    }
    if ($null -eq $run) { throw ("Workflow did not register for exact SHA {0}: {1}" -f $HeadSha, $Workflow) }

    Write-Host ("Watching run {0}: {1}" -f $run.id, $Workflow) -ForegroundColor Cyan
    while ((Get-Date) -lt $deadline) {
        $current = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runs/{1}" -f $Repository, $run.id) -Retries 5
        Write-Host ("[{0}] {1}: {2}" -f (Get-Date -Format "HH:mm:ss"), $Workflow, $current.status)
        if ($current.status -eq "completed") {
            if ($current.conclusion -ne "success") {
                Show-FailedRunDiagnostics -RunId $current.id
                throw ("Workflow failed on exact SHA {0}: {1} => {2} (run {3})" -f $HeadSha, $Workflow, $current.conclusion, $current.id)
            }
            Write-Host ("GREEN: {0} run {1}" -f $Workflow, $current.id) -ForegroundColor Green
            return $current
        }
        Start-Sleep -Seconds 15
    }
    throw ("Timed out waiting for workflow: {0}" -f $Workflow)
}

function Get-ExactHeadAuthoritativeCheck {
    param([Parameter(Mandatory = $true)][string]$HeadSha)
    $checks = Invoke-GhJson -Method GET -Path ("repos/{0}/commits/{1}/check-runs?per_page=100" -f $Repository, $HeadSha)
    foreach ($name in @($SmokeContext, $AuthoritativeContext)) {
        $latest = @($checks.check_runs | Where-Object name -eq $name | Sort-Object completed_at -Descending) | Select-Object -First 1
        if ($null -eq $latest) { throw ("Missing exact-head check: {0}" -f $name) }
        if ($latest.status -ne "completed" -or $latest.conclusion -ne "success") {
            throw ("Exact-head check is not green: {0} => {1}/{2}" -f $name, $latest.status, $latest.conclusion)
        }
    }
    $auth = @($checks.check_runs | Where-Object name -eq $AuthoritativeContext | Sort-Object completed_at -Descending) | Select-Object -First 1
    if ($null -eq $auth.app -or -not $auth.app.id) { throw "Cannot resolve GitHub Actions integration id." }
    return $auth
}

function Cutover-Ruleset {
    param([Parameter(Mandatory = $true)]$AuthoritativeCheck)
    $ruleset = Get-Ruleset
    Assert-RulesetInvariant -Ruleset $ruleset
    $statusRule = $ruleset.rules | Where-Object type -eq "required_status_checks" | Select-Object -First 1
    $statusRule.parameters.required_status_checks = @(
        [pscustomobject]@{
            context = $AuthoritativeContext
            integration_id = [int]$AuthoritativeCheck.app.id
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
    Invoke-GhJson -Method PUT -Path ("repos/{0}/rulesets/{1}" -f $Repository, $RulesetId) -Body $body | Out-Null

    $deadline = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $deadline) {
        $verify = Get-Ruleset
        $required = @(($verify.rules | Where-Object type -eq "required_status_checks").parameters.required_status_checks)
        if ($required.Count -eq 1 -and $required[0].context -eq $AuthoritativeContext) {
            Write-Host ("Protect main cutover verified: {0}" -f $AuthoritativeContext) -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 5
    }
    throw "Ruleset cutover did not converge."
}

function Merge-PrWithPropagationWait {
    param(
        [Parameter(Mandatory = $true)][int]$Number,
        [Parameter(Mandatory = $true)][string]$ExpectedHead
    )

    for ($attempt = 1; $attempt -le 18; $attempt++) {
        try {
            $pr = Invoke-GhJson -Method GET -Path ("repos/{0}/pulls/{1}" -f $Repository, $Number) -Retries 4
            if ($pr.merged) { return $pr.merge_commit_sha }
            if ($pr.head.sha -ne $ExpectedHead) { throw "PR head changed after exact-head validation." }

            $merge = Invoke-GhJson -Method PUT -Path ("repos/{0}/pulls/{1}/merge" -f $Repository, $Number) -Body @{
                merge_method = "squash"
                sha = $ExpectedHead
                commit_title = ("Infra: GitHub Pro hybrid CI + Lenovo continuity (#{0})" -f $Number)
                commit_message = "Finalize hybrid CI with GitHub-hosted acceleration and Lenovo authoritative continuity."
            } -Retries 2
            if ($merge.merged) {
                Write-Host ("Merged PR #{0}: {1}" -f $Number, $merge.sha) -ForegroundColor Green
                return $merge.sha
            }
        } catch {
            if ($attempt -ge 18) { throw }
            Write-Host ("Waiting for ruleset/check propagation before merge ({0}/18): {1}" -f $attempt, $_.Exception.Message) -ForegroundColor Yellow
            Start-Sleep -Seconds 10
        }
    }
    throw "Infrastructure PR did not become mergeable after ruleset cutover."
}

function Verify-FinalState {
    $ruleset = Get-Ruleset
    Assert-RulesetInvariant -Ruleset $ruleset
    $required = @(($ruleset.rules | Where-Object type -eq "required_status_checks").parameters.required_status_checks)
    if ($required.Count -ne 1 -or $required[0].context -ne $AuthoritativeContext) {
        throw "Protect main must require exactly the authoritative self-hosted gate."
    }
    $workflowPolicy = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/permissions/workflow" -f $Repository)
    if ($workflowPolicy.default_workflow_permissions -ne "read") { throw "Default GITHUB_TOKEN must remain read-only." }
    if ($workflowPolicy.can_approve_pull_request_reviews) { throw "Actions must not approve pull requests." }
    Write-Host "FINAL VERIFY: PASS" -ForegroundColor Green
    Write-Host ("Required merge context: {0}" -f $required[0].context)
    Write-Host ("Default GITHUB_TOKEN: {0}" -f $workflowPolicy.default_workflow_permissions)
}

Write-Host "=== Omni-CIO GitHub hybrid CI finalizer v2 ===" -ForegroundColor Cyan
Write-Host "Lenovo: authoritative protected-runtime regression/security." -ForegroundColor Cyan
Write-Host "GitHub-hosted: independent fast + clean Python 3.14/Node 24 compatibility acceleration." -ForegroundColor Cyan

Assert-SessionAndRepository
Wait-RunnerReady | Out-Null
$ruleset = Get-Ruleset
Assert-RulesetInvariant -Ruleset $ruleset
$pr = Get-OpenInfrastructurePr

if ($pr.merged) {
    $main = Invoke-GhJson -Method GET -Path ("repos/{0}/branches/main" -f $Repository)
    $mainSha = $main.commit.sha
    Write-Host ("PR #{0} already merged; resuming post-merge verification at {1}" -f $InfrastructurePr, $mainSha) -ForegroundColor Yellow
} else {
    $headSha = $pr.head.sha
    Write-Host ("Exact infrastructure head: {0}" -f $headSha) -ForegroundColor Cyan
    Dispatch-Workflow -Workflow $SelfHostedWorkflow -Ref $InfrastructureBranch
    Wait-WorkflowExactHead -Workflow $SelfHostedWorkflow -Branch $InfrastructureBranch -HeadSha $headSha -TimeoutMinutes $PreMergeTimeoutMinutes | Out-Null
    $authoritative = Get-ExactHeadAuthoritativeCheck -HeadSha $headSha
    Cutover-Ruleset -AuthoritativeCheck $authoritative
    $mainSha = Merge-PrWithPropagationWait -Number $InfrastructurePr -ExpectedHead $headSha
}

Write-Host ("Post-merge main SHA: {0}" -f $mainSha) -ForegroundColor Cyan
Dispatch-Workflow -Workflow $RegressionWorkflow -Ref "main"
Wait-WorkflowExactHead -Workflow $RegressionWorkflow -Branch "main" -HeadSha $mainSha -TimeoutMinutes $PostMergeTimeoutMinutes | Out-Null
Verify-FinalState
Write-Host "GITHUB HYBRID CI FINALIZATION COMPLETE. WP4 remains untouched." -ForegroundColor Green
