[CmdletBinding()]
param(
    [string]$Repository = "MishaGameHacking/omni-cio-gateway",
    [int]$RulesetId = 20519289,
    [int]$InfrastructurePr = 242,
    [string]$InfrastructureBranch = "infra/github-pro-hybrid-ci",
    [int]$PreMergeTimeoutMinutes = 45,
    [int]$PostMergeTimeoutMinutes = 70,
    [int]$ApiRetries = 20
)

$ErrorActionPreference = "Stop"
$ApiVersion = "2026-03-10"
$ExpectedOwner = "MishaGameHacking"
$AuthoritativeContext = "V10 authoritative merge gate"
$SmokeContext = "Windows runner smoke test"
$SelfHostedWorkflow = "self-hosted-windows-smoke.yml"
$RegressionWorkflow = "regression-shield.yml"

function Invoke-GhJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body = $null,
        [int]$Retries = $ApiRetries
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        $args = @(
            "api",
            "--method", $Method,
            "-H", "Accept: application/vnd.github+json",
            "-H", ("X-GitHub-Api-Version: {0}" -f $ApiVersion),
            $Path
        )

        # Windows PowerShell 5.1 can promote native stderr from gh.exe to a
        # terminating NativeCommandError when $ErrorActionPreference is Stop.
        # Temporarily downgrade native-command errors so transient TLS/API
        # failures can be retried instead of aborting the finalizer.
        $savedErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            if ($null -eq $Body) {
                $raw = & gh @args 2>&1
            }
            else {
                $json = $Body | ConvertTo-Json -Depth 100 -Compress
                $raw = $json | & gh @args --input - 2>&1
            }
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $savedErrorActionPreference
        }

        if ($exitCode -eq 0) {
            if (-not $raw) { return $null }
            $text = ($raw | Out-String).Trim()
            if (-not $text) { return $null }
            return ($text | ConvertFrom-Json)
        }

        $detail = (($raw | Out-String).Trim() -replace "\r?\n", " | ")
        if ($detail.Length -gt 350) { $detail = $detail.Substring(0, 350) }

        if ($attempt -ge $Retries) {
            throw ("GitHub API remained unavailable after {0} attempts: {1} {2}. Last error: {3}" -f $Retries, $Method, $Path, $detail)
        }

        $delay = [Math]::Min(4 * $attempt, 30)
        Write-Host ("Transient GitHub API/Actions error. Retry {0}/{1} in {2}s: {3} {4}" -f $attempt, $Retries, $delay, $Method, $Path) -ForegroundColor Yellow
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

function Get-Runner {
    $response = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runners" -f $Repository)
    $runner = @($response.runners | Where-Object {
        $_.name -eq "omni-cio-ci" -and
        $_.status -eq "online" -and
        ($_.labels.name -contains "self-hosted") -and
        ($_.labels.name -contains "Windows") -and
        ($_.labels.name -contains "X64") -and
        ($_.labels.name -contains "omni-cio-ci")
    }) | Select-Object -First 1

    if ($null -eq $runner) {
        throw "Required online runner omni-cio-ci with self-hosted/Windows/X64/omni-cio-ci labels was not found."
    }
    Write-Host ("Runner ready: {0}, busy={1}" -f $runner.name, $runner.busy) -ForegroundColor Green
    return $runner
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

function Dispatch-Workflow {
    param(
        [Parameter(Mandatory = $true)][string]$Workflow,
        [Parameter(Mandatory = $true)][string]$Ref
    )

    Invoke-GhJson -Method POST -Path ("repos/{0}/actions/workflows/{1}/dispatches" -f $Repository, $Workflow) -Body @{ ref = $Ref } | Out-Null
    Write-Host ("Dispatched self-hosted workflow: {0} on {1}" -f $Workflow, $Ref) -ForegroundColor Cyan
}

function Wait-Workflow {
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
        $path = "repos/{0}/actions/workflows/{1}/runs?branch={2}&event=workflow_dispatch&per_page=30" -f $Repository, $Workflow, $encodedBranch
        $runs = Invoke-GhJson -Method GET -Path $path
        $run = @($runs.workflow_runs | Where-Object head_sha -eq $HeadSha | Sort-Object created_at -Descending) | Select-Object -First 1
        if ($null -ne $run) { break }
        Write-Host ("Waiting for workflow registration: {0}" -f $Workflow)
        Start-Sleep -Seconds 10
    }
    if ($null -eq $run) { throw ("Workflow did not appear for exact SHA {0}: {1}" -f $HeadSha, $Workflow) }

    Write-Host ("Watching run {0}: {1}" -f $run.id, $Workflow) -ForegroundColor Cyan
    while ((Get-Date) -lt $deadline) {
        $current = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runs/{1}" -f $Repository, $run.id)
        Write-Host ("[{0}] {1}: {2}" -f (Get-Date -Format "HH:mm:ss"), $Workflow, $current.status)
        if ($current.status -eq "completed") {
            if ($current.conclusion -ne "success") {
                throw ("Workflow failed on exact SHA {0}: {1} => {2} (run {3})" -f $HeadSha, $Workflow, $current.conclusion, $current.id)
            }
            Write-Host ("GREEN: {0} run {1}" -f $Workflow, $current.id) -ForegroundColor Green
            return $current
        }
        Start-Sleep -Seconds 15
    }

    throw ("Timed out waiting for workflow: {0}" -f $Workflow)
}

function Get-CheckRuns {
    param([Parameter(Mandatory = $true)][string]$Sha)
    return Invoke-GhJson -Method GET -Path ("repos/{0}/commits/{1}/check-runs?per_page=100" -f $Repository, $Sha)
}

function Assert-SelfHostedPreMergeGreen {
    param([Parameter(Mandatory = $true)][string]$HeadSha)

    $checks = Get-CheckRuns -Sha $HeadSha
    foreach ($name in @($SmokeContext, $AuthoritativeContext)) {
        $latest = @($checks.check_runs | Where-Object name -eq $name | Sort-Object completed_at -Descending) | Select-Object -First 1
        if ($null -eq $latest) { throw ("Missing exact-head self-hosted check: {0}" -f $name) }
        if ($latest.status -ne "completed" -or $latest.conclusion -ne "success") {
            throw ("Self-hosted check is not green: {0} => {1}/{2}" -f $name, $latest.status, $latest.conclusion)
        }
    }

    $authoritative = @($checks.check_runs | Where-Object name -eq $AuthoritativeContext | Sort-Object completed_at -Descending) | Select-Object -First 1
    if ($null -eq $authoritative.app -or -not $authoritative.app.id) { throw "Cannot resolve GitHub Actions app id for authoritative check." }
    return $authoritative
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
    Write-Host ("Protect main now requires only: {0}" -f $AuthoritativeContext) -ForegroundColor Green
}

function Assert-BranchUpToDate {
    param([Parameter(Mandatory = $true)]$Pr)

    $main = Invoke-GhJson -Method GET -Path ("repos/{0}/branches/main" -f $Repository)
    if ($Pr.base.sha -ne $main.commit.sha) {
        throw ("Infrastructure PR is not up to date with main. PR base={0}, main={1}" -f $Pr.base.sha, $main.commit.sha)
    }
}

function Merge-Pr {
    param(
        [Parameter(Mandatory = $true)][int]$Number,
        [Parameter(Mandatory = $true)][string]$ExpectedHead
    )

    $merge = Invoke-GhJson -Method PUT -Path ("repos/{0}/pulls/{1}/merge" -f $Repository, $Number) -Body @{
        merge_method = "squash"
        sha = $ExpectedHead
        commit_title = ("Infra: GitHub Pro hybrid CI + Lenovo continuity (#{0})" -f $Number)
        commit_message = "Finalize hybrid CI with self-hosted authoritative continuity during GitHub Actions incident."
    }
    if (-not $merge.merged) { throw ("Infrastructure PR merge failed: {0}" -f $merge.message) }
    Write-Host ("Merged PR #{0}: {1}" -f $Number, $merge.sha) -ForegroundColor Green
    return $merge.sha
}

function Verify-FinalState {
    $ruleset = Get-Ruleset
    Assert-RulesetInvariant -Ruleset $ruleset
    $required = @(($ruleset.rules | Where-Object type -eq "required_status_checks").parameters.required_status_checks)
    if ($required.Count -ne 1 -or $required[0].context -ne $AuthoritativeContext) {
        throw "Protect main must require only the authoritative self-hosted gate."
    }

    $workflowPolicy = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/permissions/workflow" -f $Repository)
    if ($workflowPolicy.default_workflow_permissions -ne "read") { throw "Default GITHUB_TOKEN must remain read-only." }
    if ($workflowPolicy.can_approve_pull_request_reviews) { throw "Actions must not approve pull requests." }

    Write-Host "FINAL VERIFY: PASS" -ForegroundColor Green
    Write-Host ("Required merge context: {0}" -f $required[0].context)
    Write-Host ("Default GITHUB_TOKEN: {0}" -f $workflowPolicy.default_workflow_permissions)
}

Write-Host "=== GitHub Actions outage-safe finalizer ===" -ForegroundColor Cyan
Write-Host "GitHub-hosted acceleration is intentionally skipped; Lenovo remains authoritative." -ForegroundColor Yellow

Assert-SessionAndRepository
$runner = Get-Runner
$ruleset = Get-Ruleset
Assert-RulesetInvariant -Ruleset $ruleset

$pr = Invoke-GhJson -Method GET -Path ("repos/{0}/pulls/{1}" -f $Repository, $InfrastructurePr)

if ($pr.merged) {
    Write-Host ("PR #{0} is already merged; resuming post-merge verification." -f $InfrastructurePr) -ForegroundColor Yellow
    $main = Invoke-GhJson -Method GET -Path ("repos/{0}/branches/main" -f $Repository)
    $mainSha = $main.commit.sha
}
else {
    if ($pr.state -ne "open") { throw ("Infrastructure PR #{0} is neither open nor merged." -f $InfrastructurePr) }
    if ($pr.head.ref -ne $InfrastructureBranch -or $pr.base.ref -ne "main") { throw "Infrastructure PR refs are unexpected." }
    if ($pr.draft) { throw "Infrastructure PR must not be draft." }
    Assert-BranchUpToDate -Pr $pr

    $headSha = $pr.head.sha
    Write-Host ("Exact infrastructure head: {0}" -f $headSha)

    Dispatch-Workflow -Workflow $SelfHostedWorkflow -Ref $InfrastructureBranch
    Wait-Workflow -Workflow $SelfHostedWorkflow -Branch $InfrastructureBranch -HeadSha $headSha -TimeoutMinutes $PreMergeTimeoutMinutes | Out-Null

    $authoritative = Assert-SelfHostedPreMergeGreen -HeadSha $headSha

    $prAfterRun = Invoke-GhJson -Method GET -Path ("repos/{0}/pulls/{1}" -f $Repository, $InfrastructurePr)
    if ($prAfterRun.head.sha -ne $headSha) { throw "PR head moved after authoritative validation; refusing to merge." }
    Assert-BranchUpToDate -Pr $prAfterRun

    Cutover-Ruleset -AuthoritativeCheck $authoritative
    $mainSha = Merge-Pr -Number $InfrastructurePr -ExpectedHead $headSha
}

Write-Host ("Post-merge main SHA: {0}" -f $mainSha)
Dispatch-Workflow -Workflow $RegressionWorkflow -Ref "main"
Wait-Workflow -Workflow $RegressionWorkflow -Branch "main" -HeadSha $mainSha -TimeoutMinutes $PostMergeTimeoutMinutes | Out-Null

Verify-FinalState
Write-Host "GITHUB OUTAGE-SAFE FINALIZATION COMPLETE. Hosted acceleration remains configured for recovery." -ForegroundColor Green
