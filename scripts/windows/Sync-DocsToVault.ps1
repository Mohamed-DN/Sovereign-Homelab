<#
.SYNOPSIS
    Mirror this repository's docs/ into the live Obsidian vault, one-way.

.DESCRIPTION
    Repo docs/ is the source of truth; the vault is a read-mostly copy that
    Hermes and Momo already index and that every synced device can browse
    offline. The direction never reverses: writing to CouchDB/the vault from
    outside Obsidian's own sync would corrupt LiveSync's chunked note format,
    which is exactly why Hermes' own vault-write tool is confined to a single
    separate folder (07 Notes/Hermes/) instead of writing docs here directly.

      repo docs/ --(this script, on the PC)--> vault folder --(LiveSync)--> CouchDB --> Hermes/Momo

    Uses robocopy /MIR so the destination folder always matches docs/
    exactly (added, changed, and removed files) -- but /MIR is a mirror, and
    a mirror pointed at the wrong folder deletes things it shouldn't. Two
    guards against that:
      - the destination is hard-coded to end in \Sovereign-Homelab, and the
        script refuses to run against anything else;
      - the destination is a dedicated subfolder nobody else writes to, never
        the vault root, never 07 Notes/Hermes/ (Hermes' own write area).

    Copies only *.md and *.png/*.jpg/*.svg (diagrams referenced from docs);
    docs/ is markdown by convention (see docs/00_overview/PIANO_GENERALE.md
    point 17: "documentazione e README nel vault; codice sorgente sui
    database"), and this filter keeps it that way even if something else
    ever lands in docs/ by mistake.

.NOTES
    Meant to run from Windows Task Scheduler (see
    SyncDocsToVault.Task.xml), or on demand after a commit. Safe to run
    repeatedly: robocopy /MIR is idempotent when nothing changed.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "C:\DBA\Sovereign-Homelab",
    [string]$VaultRoot = "C:\Users\Mohamed\Documents\VaultMohamed\VaultMohamed",
    [string]$VaultSubfolder = "Sovereign-Homelab"
)

$ErrorActionPreference = "Stop"

$source = Join-Path $RepoRoot "docs"
$destination = Join-Path $VaultRoot $VaultSubfolder
$logDir = Join-Path $RepoRoot "logs\docs-to-vault"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("sync-" + (Get-Date -Format "yyyyMMdd") + ".log")

function Write-Log([string]$Message) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
    Write-Host $line
}

Write-Log "Docs -> vault sync starting."

# Guard: the destination must be exactly <VaultRoot>\Sovereign-Homelab, never
# the vault root or another folder. /MIR deletes what isn't in the source, so
# a wrong destination here is a data-loss bug, not a cosmetic one.
if ((Split-Path -Leaf $destination) -ne "Sovereign-Homelab") {
    Write-Log "REFUSING to run: destination '$destination' does not end in \Sovereign-Homelab."
    exit 1
}
if (-not (Test-Path -LiteralPath $source)) {
    Write-Log "REFUSING to run: source '$source' does not exist."
    exit 1
}
if (-not (Test-Path -LiteralPath $VaultRoot)) {
    Write-Log "REFUSING to run: vault root '$VaultRoot' does not exist. Is the vault path still correct?"
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $VaultRoot ".obsidian"))) {
    Write-Log "REFUSING to run: '$VaultRoot' has no .obsidian folder -- this does not look like the live vault."
    exit 1
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null

Write-Log "Mirroring '$source' -> '$destination' (*.md, *.png, *.jpg, *.svg only)."

# /MIR mirrors the tree (add, update, delete to match source).
# /XF excludes non-doc file types that should never end up in the vault.
# /NFL /NDL /NP keep the console/log quiet; /R:2 /W:2 avoid long hangs on a
# transient file lock (e.g. an editor holding a file open).
$robocopyArgs = @(
    $source, $destination,
    "*.md", "*.png", "*.jpg", "*.jpeg", "*.svg",
    "/MIR", "/R:2", "/W:2", "/NFL", "/NDL", "/NP", "/NJH"
)
$output = & robocopy @robocopyArgs 2>&1
$exit = $LASTEXITCODE
$output | ForEach-Object { Write-Log $_ }

# Robocopy's exit codes are a bitmask, not a plain success/fail code: 0-7 are
# all success (0 = nothing to do, 1 = files copied, etc.); 8+ means failure.
if ($exit -lt 8) {
    Write-Log "Sync completed (robocopy exit $exit -- success range)."
    exit 0
} else {
    Write-Log "Sync FAILED (robocopy exit $exit -- see https://ss64.com/nt/robocopy-exit.html)."
    exit 1
}
