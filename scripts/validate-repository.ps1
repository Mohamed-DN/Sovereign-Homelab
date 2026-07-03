[CmdletBinding()]
param(
    [switch]$SkipCompose
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$failures = [System.Collections.Generic.List[string]]::new()
$passes = [System.Collections.Generic.List[string]]::new()

function Add-Pass([string]$Message) {
    $passes.Add($Message)
}

function Add-Failure([string]$Message) {
    $failures.Add($Message)
}

function Get-RelativePath([string]$Path) {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if ($fullPath.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $fullPath.Substring($repoRoot.Length).TrimStart('\', '/').Replace('\', '/')
    }
    return $fullPath.Replace('\', '/')
}

Push-Location $repoRoot
try {
    $savedErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $diffCheck = & git diff --check 2>&1
    $ErrorActionPreference = $savedErrorPreference
    if ($LASTEXITCODE -eq 0) { Add-Pass 'git diff --check' } else { Add-Failure "git diff --check: $diffCheck" }

    $markdownFiles = Get-ChildItem -Path README.md, START_HERE.md, OPERATIONAL_GUIDE.md, docs, stacks, scripts -Recurse -File -Include *.md
    $linkPattern = [regex]'!?(?:\[[^\]]*\])\((?<target>[^)]+)\)'
    foreach ($file in $markdownFiles) {
        $content = Get-Content -LiteralPath $file.FullName -Raw
        foreach ($match in $linkPattern.Matches($content)) {
            $target = $match.Groups['target'].Value.Trim().Trim('<', '>')
            if ($target -match '^(?:https?://|mailto:|#)' -or $target -eq '') { continue }
            $pathOnly = [uri]::UnescapeDataString(($target -split '#', 2)[0])
            if ($pathOnly -match ':[0-9]+$') { $pathOnly = $pathOnly -replace ':[0-9]+$', '' }
            $resolved = Join-Path $file.DirectoryName $pathOnly
            if (-not (Test-Path -LiteralPath $resolved)) {
                Add-Failure "broken Markdown link in $(Get-RelativePath $file.FullName): $target"
            }
        }
    }
    if (-not ($failures | Where-Object { $_ -like 'broken Markdown link*' })) { Add-Pass 'local Markdown links' }

    $scanFiles = Get-ChildItem -Path README.md, START_HERE.md, OPERATIONAL_GUIDE.md, docs, stacks, scripts -Recurse -File |
        Where-Object { $_.Extension -in '.md', '.yml', '.yaml', '.example', '.sh', '.ps1', '.py', '.html', '.txt' }
    $forbiddenNaming = [regex]'(?i)(?:\b[a-z][a-z0-9-]*\.(?:local|home|lan|x)(?=[:/\s`)\]]|$)|home\.arpa\b|it[-_]home\b)'
    $privateDuckDns = [regex]'(?i)\b(?:dash|status|monitor|logs|pwd|foto|files|auth|npm|adguard|pbs|proxmox)\.[a-z0-9-]+\.duckdns\.org\b'
    $secretPattern = [regex]'(?i)(?:BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|AKIA[0-9A-Z]{16}|(?:smtp[_-]?password|duckdns[_-]?token)\s*[:=]\s*["''][^"''<\s][^"'']*["''])'
    foreach ($file in $scanFiles) {
        if ((Get-RelativePath $file.FullName) -eq 'docs/99_reference/VALIDATION_COMMANDS.md') { continue }
        $content = Get-Content -LiteralPath $file.FullName -Raw
        if ($forbiddenNaming.IsMatch($content)) { Add-Failure "forbidden private namespace in $(Get-RelativePath $file.FullName)" }
        if ($privateDuckDns.IsMatch($content)) { Add-Failure "private application DuckDNS name in $(Get-RelativePath $file.FullName)" }
        if ($secretPattern.IsMatch($content)) { Add-Failure "secret-like value in $(Get-RelativePath $file.FullName)" }
    }
    if (-not ($failures | Where-Object { $_ -like 'forbidden private namespace*' -or $_ -like 'private application DuckDNS*' })) { Add-Pass 'private DNS policy' }
    if (-not ($failures | Where-Object { $_ -like 'secret-like value*' })) { Add-Pass 'repository secret patterns' }

    $composeFiles = Get-ChildItem stacks -Recurse -File -Filter docker-compose.yml
    foreach ($compose in $composeFiles) {
        $stackDir = $compose.Directory.FullName
        $envExample = Join-Path $stackDir '.env.example'
        $composeText = Get-Content -LiteralPath $compose.FullName -Raw
        $variables = [regex]::Matches($composeText, '\$\{(?<name>[A-Z_][A-Z0-9_]*)') |
            ForEach-Object { $_.Groups['name'].Value } | Sort-Object -Unique
        if ($variables.Count -gt 0 -and -not (Test-Path -LiteralPath $envExample)) {
            Add-Failure "missing .env.example for $(Get-RelativePath $compose.FullName)"
            continue
        }
        if (Test-Path -LiteralPath $envExample) {
            $defined = Get-Content -LiteralPath $envExample |
                Where-Object { $_ -match '^\s*(?<name>[A-Z_][A-Z0-9_]*)=' } |
                ForEach-Object { $Matches['name'] }
            foreach ($variable in $variables) {
                if ($variable -notin $defined) {
                    Add-Failure "undefined Compose variable $variable in $(Get-RelativePath $compose.FullName)"
                }
            }
        }
        foreach ($line in ($composeText -split "`n")) {
            if ($line -match '(?i)^\s*image:\s*[^#\r\n]+:(latest|main|release)\s*$') {
                $allowed = $line -match 'nextcloud-releases/all-in-one:latest|netalertx/netalertx:latest'
                if (-not $allowed) { Add-Failure "rolling image tag in $(Get-RelativePath $compose.FullName): $($line.Trim())" }
            }
        }
    }
    if (-not ($failures | Where-Object { $_ -like '*Compose variable*' -or $_ -like 'missing .env.example*' })) { Add-Pass 'Compose environment coverage' }
    if (-not ($failures | Where-Object { $_ -like 'rolling image tag*' })) { Add-Pass 'pinned image policy' }

    $excludedGuides = @('00_APP_SERVICES_INDEX.md', 'common_docker_app_pattern.md', 'doc_10_core_apps.md', 'production_acceptance_checklist.md')
    $appGuides = Get-ChildItem docs/04_apps -File -Filter *.md | Where-Object { $_.Name -notin $excludedGuides }
    $contract = [ordered]@{
        purpose = '(?i)(purpose|overview|architecture)'
        target = '(?i)(target|sizing)'
        install = '(?i)(install|deployment)'
        dns = '(?i)(dns|domain names|alias)'
        npm = '(?i)(nginx proxy manager|\bNPM\b)'
        homepage = '(?i)Homepage'
        kuma = '(?i)Uptime Kuma'
        backup = '(?i)backup'
        restore = '(?i)restore'
        rollback = '(?i)rollback'
        troubleshooting = '(?i)troubleshooting'
        sources = '(?i)(##\s+(?:\d+\.\s+)?(?:Official\s+)?Sources|\*Sources?:)'
    }
    foreach ($guide in $appGuides) {
        $content = Get-Content -LiteralPath $guide.FullName -Raw
        foreach ($entry in $contract.GetEnumerator()) {
            if ($content -notmatch $entry.Value) {
                Add-Failure "app runbook contract '$($entry.Key)' missing in $(Get-RelativePath $guide.FullName)"
            }
        }
    }
    if (-not ($failures | Where-Object { $_ -like 'app runbook contract*' })) { Add-Pass 'application runbook contract' }

    $homepage = Get-Content stacks/observability/homepage/services.yaml -Raw
    $ids = [regex]::Matches($homepage, '(?m)^\s+id:\s*(?<id>[a-z0-9-]+)\s*$') | ForEach-Object { $_.Groups['id'].Value }
    $duplicateIds = $ids | Group-Object | Where-Object Count -gt 1
    if ($duplicateIds) { Add-Failure "duplicate Homepage IDs: $($duplicateIds.Name -join ', ')" } else { Add-Pass 'unique Homepage IDs' }
    $hrefs = [regex]::Matches($homepage, '(?m)^\s+href:\s*(?<url>\S+)\s*$') | ForEach-Object { $_.Groups['url'].Value }
    foreach ($href in $hrefs) {
        if ($href -notmatch '^https://(?:[a-z0-9-]+\.internal|vpn\.yourdomain\.duckdns\.org)(?:[:/]|$)') {
            Add-Failure "Homepage link violates private-access policy: $href"
        }
    }
    if (-not ($failures | Where-Object { $_ -like 'Homepage link violates*' })) { Add-Pass 'Homepage alias policy' }

    if (-not $SkipCompose) {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            Add-Failure 'Docker is unavailable; rerun with -SkipCompose only when template validation is intentionally deferred'
        } else {
            foreach ($compose in $composeFiles) {
                $envExample = Join-Path $compose.Directory.FullName '.env.example'
                $arguments = @('compose')
                if (Test-Path -LiteralPath $envExample) { $arguments += @('--env-file', $envExample) }
                $arguments += @('-f', $compose.FullName, 'config', '--quiet')
                & docker @arguments 2>&1 | Out-Null
                if ($LASTEXITCODE -ne 0) { Add-Failure "Compose validation failed: $(Get-RelativePath $compose.FullName)" }
            }
            if (-not ($failures | Where-Object { $_ -like 'Compose validation failed*' })) { Add-Pass 'Compose template rendering' }
        }
    }

    foreach ($pass in $passes) { Write-Host "PASS $pass" -ForegroundColor Green }
    if ($failures.Count -gt 0) {
        foreach ($failure in $failures) { Write-Host "FAIL $failure" -ForegroundColor Red }
        Write-Host "RESULT failed: $($failures.Count) issue(s)" -ForegroundColor Red
        exit 1
    }
    Write-Host "RESULT passed: $($passes.Count) validation groups" -ForegroundColor Green
}
finally {
    Pop-Location
}
