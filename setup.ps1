<#
  Infra Radar - one-shot setup for Windows.

      .\setup.ps1                 # repo named infra-radar
      .\setup.ps1 -RepoName notes # or pick your own name

  Creates the GitHub repo, pushes the archive, sets the secrets and variables,
  turns on Pages, and kicks off the first run.
#>

[CmdletBinding()]
param(
    [string]$RepoName = "infra-radar"
)

# Native commands here are checked explicitly via $LASTEXITCODE. PowerShell 7.4+
# turns non-zero native exits into terminating errors when both of these are on,
# which would abort on expected failures like "gh auth status" when logged out.
$ErrorActionPreference = "Continue"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Say  { param($m) Write-Host $m -ForegroundColor White }
function Ok   { param($m) Write-Host "  [ok] $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Note { param($m) Write-Host "       $m" -ForegroundColor DarkGray }
function Die  { param($m) Write-Host "`n  [x] $m`n" -ForegroundColor Red; exit 1 }

function Read-Secret {
    param($Prompt)
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try   { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

Set-Location -Path $PSScriptRoot

# ------------------------------------------------------------------ preflight

Say ""
Say "Checking prerequisites..."

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Say ""
    Say "Git isn't installed. Install it with:"
    Note "winget install --id Git.Git -e"
    Note "then close and reopen PowerShell and run this script again."
    Die "Git required."
}
Ok "git"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Say ""
    Say "The GitHub CLI isn't installed. Install it with:"
    Note "winget install --id GitHub.cli -e"
    Note "then close and reopen PowerShell and run this script again."
    Die "GitHub CLI required."
}
Ok "gh"

gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Say ""
    Say "Logging you into GitHub (a browser window will open)..."
    gh auth login
    if ($LASTEXITCODE -ne 0) { Die "GitHub login did not complete." }
}

$Owner = gh api user --jq .login
if ([string]::IsNullOrWhiteSpace($Owner)) { Die "Could not read your GitHub username. Try: gh auth login" }
$Owner = $Owner.Trim()
Ok "authenticated as $Owner"

# --------------------------------------------------------------------- inputs

Say ""
Say "Anthropic API key"
Note "From console.anthropic.com - this is what pays for the daily run."
Note "It will not appear as you paste. That's expected."
$AnthropicKey = Read-Secret "  ANTHROPIC_API_KEY"
if ([string]::IsNullOrWhiteSpace($AnthropicKey)) { Die "An API key is required." }
if (-not $AnthropicKey.StartsWith("sk-ant-")) {
    Warn "That doesn't start with 'sk-ant-'. Continuing anyway, but double-check it."
}

Say ""
Say "Morning email (optional - press Enter to skip, you can add it later)"
$MailUser = Read-Host "  Gmail address"
$MailPass = $null
$EmailTo  = $null
if (-not [string]::IsNullOrWhiteSpace($MailUser)) {
    Note "Use a Gmail APP PASSWORD, not your normal password:"
    Note "Google Account > Security > 2-Step Verification > App passwords"
    $MailPass = Read-Secret "  App password"
    $EmailTo  = Read-Host "  Send digest to [$MailUser]"
    if ([string]::IsNullOrWhiteSpace($EmailTo)) { $EmailTo = $MailUser }
}

# ----------------------------------------------------------------------- repo

Say ""
Say "Creating $Owner/$RepoName ..."

if (-not (Test-Path ".git")) {
    git init -q -b main
    if ($LASTEXITCODE -ne 0) { git init -q; git checkout -q -b main }

    $cfgName = (git config user.name)
    if ([string]::IsNullOrWhiteSpace($cfgName)) {
        git config user.name  $Owner
        git config user.email "$Owner@users.noreply.github.com"
    }
    git add -A
    git commit -q -m "Infra Radar: initial archive and pipeline"
    if ($LASTEXITCODE -ne 0) { Die "git commit failed." }
}

gh repo view "$Owner/$RepoName" *> $null
if ($LASTEXITCODE -eq 0) {
    Warn "Repo already exists - pushing to it."
    git remote remove origin *> $null
    git remote add origin "https://github.com/$Owner/$RepoName.git"
    git push -u origin main
} else {
    gh repo create $RepoName --public --source=. --remote=origin --push
}
if ($LASTEXITCODE -ne 0) { Die "Push failed. Check the message above." }
Ok "pushed"

$SiteUrl = "https://$Owner.github.io/$RepoName"

# --------------------------------------------------------- secrets and config

Say ""
Say "Setting secrets and variables..."

gh secret set ANTHROPIC_API_KEY --repo "$Owner/$RepoName" --body $AnthropicKey
if ($LASTEXITCODE -ne 0) { Die "Could not set ANTHROPIC_API_KEY." }
Ok "ANTHROPIC_API_KEY"

if ($MailPass) {
    gh secret   set MAIL_USERNAME --repo "$Owner/$RepoName" --body $MailUser
    gh secret   set MAIL_PASSWORD --repo "$Owner/$RepoName" --body $MailPass
    gh variable set EMAIL_TO      --repo "$Owner/$RepoName" --body $EmailTo
    Ok "email configured -> $EmailTo"
} else {
    Note "Email skipped. The workflow detects this and stays quiet."
    Note "To add it later, see 'Turning the email on later' in README.md"
}

gh variable set SITE_URL --repo "$Owner/$RepoName" --body $SiteUrl
Ok "SITE_URL"

# ---------------------------------------------------------------------- pages

Say ""
Say "Turning on GitHub Pages..."
'{"source":{"branch":"main","path":"/"}}' | gh api -X POST "repos/$Owner/$RepoName/pages" --input - *> $null
if ($LASTEXITCODE -eq 0) {
    Ok "Pages enabled"
} else {
    gh api "repos/$Owner/$RepoName/pages" *> $null
    if ($LASTEXITCODE -eq 0) {
        Ok "Pages already enabled"
    } else {
        Warn "Enable it by hand: Settings > Pages > Deploy from a branch > main / (root)"
    }
}

# ------------------------------------------------------------------ first run

Say ""
$RunNow = Read-Host "Run the first brief now? [Y/n]"
if ($RunNow -notmatch '^[Nn]') {
    gh workflow run daily.yml --repo "$Owner/$RepoName" -f lookback_days=2
    if ($LASTEXITCODE -eq 0) {
        Ok "triggered"
        Note "Watch it:  gh run watch --repo $Owner/$RepoName"
    } else {
        Warn "Could not trigger. Run it from the Actions tab instead."
    }
}

Say ""
Write-Host "  Done." -ForegroundColor Green
Say ""
Say "  Site     $SiteUrl/"
Say "  Repo     https://github.com/$Owner/$RepoName"
Say "  Actions  https://github.com/$Owner/$RepoName/actions"
Say ""
Note "Pages takes a minute or two to publish the first time."
Note "After that the cron runs every weekday at 6:30am ET and the site updates itself."
Say ""
