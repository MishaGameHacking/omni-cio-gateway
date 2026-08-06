[CmdletBinding()]
param(
    [switch]$Finalize,
    [switch]$Verify,
    [string]$Repository = "MishaGameHacking/omni-cio-gateway",
    [int]$RulesetId = 20519289,
    [int]$RetentionDays = 7,
    [int]$WorkflowTimeoutMinutes = 110
)

$ErrorActionPreference = "Stop"
$ApiVersion = "2026-03-10"
$ExpectedOwner = "MishaGameHacking"
$ExpectedRepo = "omni-cio-gateway"
$InfrastructurePr = 242
$InfrastructureBranch = "infra/github-pro-hybrid-ci"
$AuthoritativeContext = "V10 authoritative merge gate"
$Workflows = @(
    "v10-pr-fast-checks.yml",
    "v10-toolchain-compat.yml",
    "self-hosted-windows-smoke.yml"
)

function Invoke-GhJson {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body = $null
    )

    $args = @(
        "api",
        "--method", $Method,
        "-H", "Accept: application/vnd.github+json",
        "-H", ("X-GitHub-Api-Version: {0}" -f $ApiVersion),
        $Path
    )

    if ($null -eq $Body) {
        $raw = & gh @args
    }
    else {
        $json = $Body | ConvertTo-Json -Depth 100 -Compress
        $raw = $json | & gh @args --input -
    }

    if ($LASTEXITCODE -ne 0) {
        throw ("GitHub API request failed: {0} {1}" -f $Method, $Path)
    }
    if (-not $raw) { return $null }
    return ($raw | ConvertFrom-Json)
}

function Assert-OwnerSession {
    $status = (& gh auth status 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated."
    }
    if ($status -notmatch ("account\s+{0}" -f [regex]::Escape($ExpectedOwner))) {
        throw ("Active GitHub CLI account must be {0}." -f $ExpectedOwner)
    }

    $repo = Invoke-GhJson -Method GET -Path ("repos/{0}" -f $Repository)
    if ($repo.owner.login -ne $ExpectedOwner -or $repo.name -ne $ExpectedRepo) {
        throw ("Repository identity mismatch: {0}" -f $repo.full_name)
    }
    if (-not $repo.private) { throw "Repository must remain private." }
}

function Get-RunnerState {
    $response = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runners" -f $Repository)
    $runner = @($response.runners | Where-Object {
        $_.name -eq "omni-cio-ci" -and
        ($_.labels.name -contains "self-hosted") -and
        ($_.labels.name -contains "Windows") -and
        ($_.labels.name -contains "X64") -and
        ($_.labels.name -contains "omni-cio-ci")
    }) | Select-Object -First 1

    if ($null -eq $runner) {
        throw "Required runner omni-cio-ci with self-hosted/Windows/X64/omni-cio-ci labels was not found."
    }
    if ($runner.status -ne "online") {
        throw ("Runner omni-cio-ci is not online. Status={0}" -f $runner.status)
    }
    return $runner
}

function Get-InfrastructurePr {
    $pr = Invoke-GhJson -Method GET -Path ("repos/{0}/pulls/{1}" -f $Repository, $InfrastructurePr)
    if ($pr.state -ne "open") { throw ("Infrastructure PR #{0} must be open." -f $InfrastructurePr) }
    if ($pr.base.ref -ne "main") { throw "Infrastructure PR must target main." }
    if ($pr.head.ref -ne $InfrastructureBranch) {
        throw ("Unexpected infrastructure branch: {0}" -f $pr.head.ref)
    }
    if ($pr.draft) { throw "Infrastructure PR must not be draft." }
    return $pr
}

function Get-Ruleset {
    return Invoke-GhJson -Method GET -Path ("repos/{0}/rulesets/{1}" -f $Repository, $RulesetId)
}

function Assert-RulesetInvariant {
    param([Parameter(Mandatory = $true)]$Ruleset)

    if ($Ruleset.name -ne "Protect main") { throw "Unexpected ruleset name." }
    if ($Ruleset.target -ne "branch") { throw "Ruleset target must remain branch." }
    if ($Ruleset.enforcement -ne "active") { throw "Ruleset must remain active." }
    if (@($Ruleset.bypass_actors).Count -ne 0) { throw "Ruleset bypass list must remain empty." }
    if (@($Ruleset.conditions.ref_name.include) -notcontains "refs/heads/main") {
        throw "Ruleset must target refs/heads/main."
    }
    if (@($Ruleset.conditions.ref_name.exclude).Count -ne 0) {
        throw "Ruleset must not exclude branches."
    }

    $types = @($Ruleset.rules.type)
    foreach ($requiredType in @("deletion", "non_fast_forward", "pull_request", "required_status_checks")) {
        if ($types -notcontains $requiredType) {
            throw ("Ruleset missing mandatory rule: {0}" -f $requiredType)
        }
    }

    $prRule = $Ruleset.rules | Where-Object type -eq "pull_request" | Select-Object -First 1
    if ($prRule.parameters.required_approving_review_count -ne 0) { throw "Required approval count drifted." }
    if (-not $prRule.parameters.required_review_thread_resolution) { throw "Conversation resolution must remain required." }
    $mergeMethods = @($prRule.parameters.allowed_merge_methods)
    if ($mergeMethods.Count -ne 1 -or $mergeMethods[0] -ne "squash") {
        throw "Squash must remain the only merge method."
    }

    $statusRule = $Ruleset.rules | Where-Object type -eq "required_status_checks" | Select-Object -First 1
    if (-not $statusRule.parameters.strict_required_status_checks_policy) {
        throw "Strict required-status policy must remain enabled."
    }
    if ($statusRule.parameters.do_not_enforce_on_create) {
        throw "Status checks must remain enforced on updates."
    }
}

function Apply-RepositoryPolicy {
    if ($RetentionDays -lt 1 -or $RetentionDays -gt 400) {
        throw "RetentionDays must be 1..400 for a private repository."
    }

    Invoke-GhJson -Method PATCH -Path ("repos/{0}" -f $Repository) -Body @{
        allow_squash_merge = $true
        allow_merge_commit = $false
        allow_rebase_merge = $false
        allow_auto_merge = $false
        delete_branch_on_merge = $true
        allow_update_branch = $true
    } | Out-Null

    Invoke-GhJson -Method PUT -Path ("repos/{0}/actions/permissions" -f $Repository) -Body @{
        enabled = $true
        allowed_actions = "all"
        sha_pinning_required = $true
    } | Out-Null

    Invoke-GhJson -Method PUT -Path ("repos/{0}/actions/permissions/workflow" -f $Repository) -Body @{
        default_workflow_permissions = "read"
        can_approve_pull_request_reviews = $false
    } | Out-Null

    Invoke-GhJson -Method PUT -Path ("repos/{0}/actions/permissions/artifact-and-log-retention" -f $Repository) -Body @{
        days = $RetentionDays
    } | Out-Null

    Invoke-GhJson -Method PUT -Path ("repos/{0}/vulnerability-alerts" -f $Repository) | Out-Null
    Invoke-GhJson -Method PUT -Path ("repos/{0}/automated-security-fixes" -f $Repository) | Out-Null

    Write-Host "Applied repository and Actions policy."
}

function Start-WorkflowDispatch {
    param(
        [Parameter(Mandatory = $true)][string]$Workflow,
        [Parameter(Mandatory = $true)][string]$Ref
    )
    Invoke-GhJson -Method POST -Path ("repos/{0}/actions/workflows/{1}/dispatches" -f $Repository, $Workflow) -Body @{ ref = $Ref } | Out-Null
    Write-Host ("Dispatched: {0} on {1}" -f $Workflow, $Ref)
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
        $path = "repos/{0}/actions/workflows/{1}/runs?branch={2}&event=workflow_dispatch&per_page=20" -f $Repository, $Workflow, $encodedBranch
        $runs = Invoke-GhJson -Method GET -Path $path
        $run = @($runs.workflow_runs | Where-Object head_sha -eq $HeadSha | Sort-Object created_at -Descending) | Select-Object -First 1
        if ($null -ne $run) { break }
        Start-Sleep -Seconds 3
    }
    if ($null -eq $run) {
        throw ("Timed out waiting for {0} to appear for {1}" -f $Workflow, $HeadSha)
    }

    Write-Host ("Watching: {0} run {1}" -f $Workflow, $run.id)
    while ((Get-Date) -lt $deadline) {
        $current = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runs/{1}" -f $Repository, $run.id)
        Write-Host ("[{0}] {1}: {2}" -f (Get-Date -Format "HH:mm:ss"), $Workflow, $current.status)
        if ($current.status -eq "completed") {
            if ($current.conclusion -ne "success") {
                throw ("{0} failed for exact head {1}: {2} (run {3})" -f $Workflow, $HeadSha, $current.conclusion, $current.id)
            }
            Write-Host ("GREEN: {0} run {1}" -f $Workflow, $current.id)
            return $current
        }
        Start-Sleep -Seconds 15
    }
    throw ("Timed out waiting for {0} to complete for {1}" -f $Workflow, $HeadSha)
}

function Assert-ExactHeadChecksGreen {
    param([Parameter(Mandatory = $true)][string]$HeadSha)

    $checks = Invoke-GhJson -Method GET -Path ("repos/{0}/commits/{1}/check-runs?per_page=100" -f $Repository, $HeadSha)
    $requiredNames = @(
        "Fast policy and source contracts",
        "Fast frontend type lint unit build",
        "Python 3.14.6 V10 baseline",
        "Node 24.18.0 / React-Vite-TypeScript baseline",
        "Windows runner smoke test",
        $AuthoritativeContext
    )

    foreach ($name in $requiredNames) {
        $matching = @($checks.check_runs | Where-Object name -eq $name | Sort-Object completed_at -Descending)
        if ($matching.Count -eq 0) {
            throw ("Required exact-head check missing: {0}" -f $name)
        }
        $latest = $matching[0]
        if ($latest.status -ne "completed" -or $latest.conclusion -ne "success") {
            throw ("Required exact-head check not green: {0} => {1}/{2}" -f $name, $latest.status, $latest.conclusion)
        }
    }
    return $checks
}

function Cutover-Ruleset {
    param([Parameter(Mandatory = $true)][string]$HeadSha)

    $checks = Assert-ExactHeadChecksGreen -HeadSha $HeadSha
    $authoritativeCheck = @($checks.check_runs | Where-Object name -eq $AuthoritativeContext | Sort-Object completed_at -Descending) | Select-Object -First 1
    if ($null -eq $authoritativeCheck.app -or -not $authoritativeCheck.app.id) {
        throw "Could not resolve GitHub Actions app id for authoritative check."
    }

    $ruleset = Get-Ruleset
    Assert-RulesetInvariant -Ruleset $ruleset
    $statusRule = $ruleset.rules | Where-Object type -eq "required_status_checks" | Select-Object -First 1
    $statusRule.parameters.required_status_checks = @(
        [pscustomobject]@{
            context = $AuthoritativeContext
            integration_id = [int]$authoritativeCheck.app.id
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
    Write-Host ("Protect main cut over to: {0}" -f $AuthoritativeContext)
}

function Merge-InfrastructurePr {
    param([Parameter(Mandatory = $true)][string]$ExpectedHead)

    $body = @{
        merge_method = "squash"
        sha = $ExpectedHead
        commit_title = ("Infra: GitHub Pro hybrid CI + Lenovo continuity (#{0})" -f $InfrastructurePr)
        commit_message = "Finalize hosted acceleration with self-hosted authoritative continuity."
    }
    $merge = Invoke-GhJson -Method PUT -Path ("repos/{0}/pulls/{1}/merge" -f $Repository, $InfrastructurePr) -Body $body
    if (-not $merge.merged) {
        throw ("Infrastructure PR merge failed: {0}" -f $merge.message)
    }
    Write-Host ("Merged infrastructure PR #{0}: {1}" -f $InfrastructurePr, $merge.sha)
    return $merge.sha
}

function Wait-PostMergeRegressionShield {
    param(
        [Parameter(Mandatory = $true)][string]$MainSha,
        [int]$TimeoutMinutes = 90
    )

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $run = $null
    while ((Get-Date) -lt $deadline) {
        $path = "repos/{0}/actions/workflows/regression-shield.yml/runs?branch=main&event=push&per_page=20" -f $Repository
        $runs = Invoke-GhJson -Method GET -Path $path
        $run = @($runs.workflow_runs | Where-Object head_sha -eq $MainSha | Sort-Object created_at -Descending) | Select-Object -First 1
        if ($null -ne $run) { break }
        Start-Sleep -Seconds 3
    }
    if ($null -eq $run) {
        throw ("Post-merge Regression Shield did not appear for main SHA {0}" -f $MainSha)
    }

    while ((Get-Date) -lt $deadline) {
        $current = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/runs/{1}" -f $Repository, $run.id)
        Write-Host ("[{0}] Regression Shield: {1}" -f (Get-Date -Format "HH:mm:ss"), $current.status)
        if ($current.status -eq "completed") {
            if ($current.conclusion -ne "success") {
                throw ("Post-merge Regression Shield failed: {0} (run {1})" -f $current.conclusion, $current.id)
            }
            Write-Host ("GREEN: post-merge Regression Shield run {0}" -f $current.id)
            return $current
        }
        Start-Sleep -Seconds 15
    }
    throw "Timed out waiting for post-merge Regression Shield."
}

function Verify-FinalState {
    $repo = Invoke-GhJson -Method GET -Path ("repos/{0}" -f $Repository)
    $workflowPolicy = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/permissions/workflow" -f $Repository)
    $retention = Invoke-GhJson -Method GET -Path ("repos/{0}/actions/permissions/artifact-and-log-retention" -f $Repository)
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
    if ([int]$retention.days -ne $RetentionDays) {
        throw ("Unexpected artifact/log retention: {0}" -f $retention.days)
    }

    $required = @(($ruleset.rules | Where-Object type -eq "required_status_checks").parameters.required_status_checks)
    if ($required.Count -ne 1 -or $required[0].context -ne $AuthoritativeContext) {
        throw "Protect main must require only the authoritative continuity gate after cutover."
    }

    Write-Host "FINAL VERIFY: PASS"
    Write-Host ("Repository: {0}" -f $repo.full_name)
    Write-Host ("Main protection: {0} {1}" -f $ruleset.name, $ruleset.enforcement)
    Write-Host ("Required merge context: {0}" -f $required[0].context)
    Write-Host ("Default GITHUB_TOKEN: {0}" -f $workflowPolicy.default_workflow_permissions)
    Write-Host ("Artifact/log retention: {0} days" -f $retention.days)
}

Assert-OwnerSession
$runner = Get-RunnerState
Write-Host ("Runner: {0} {1} busy={2}" -f $runner.name, $runner.status, $runner.busy)

if ($Finalize) {
    Apply-RepositoryPolicy
    $pr = Get-InfrastructurePr
    $head = $pr.head.sha
    Write-Host ("Exact infrastructure head: {0}" -f $head)

    foreach ($workflow in $Workflows) {
        Start-WorkflowDispatch -Workflow $workflow -Ref $InfrastructureBranch
    }
    foreach ($workflow in $Workflows) {
        Wait-WorkflowForHead -Workflow $workflow -HeadSha $head -Branch $InfrastructureBranch -TimeoutMinutes $WorkflowTimeoutMinutes | Out-Null
    }

    $currentPr = Get-InfrastructurePr
    if ($currentPr.head.sha -ne $head) {
        throw ("PR head moved during finalization. Expected {0}, got {1}." -f $head, $currentPr.head.sha)
    }

    Cutover-Ruleset -HeadSha $head
    $mainSha = Merge-InfrastructurePr -ExpectedHead $head
    Wait-PostMergeRegressionShield -MainSha $mainSha -TimeoutMinutes 90 | Out-Null
    Verify-FinalState
    Write-Host "GITHUB HYBRID CI FINALIZATION COMPLETE. WP4 remains untouched."
    exit 0
}

if ($Verify) {
    Verify-FinalState
    exit 0
}

Write-Host "No action selected. Use -Finalize or -Verify."
