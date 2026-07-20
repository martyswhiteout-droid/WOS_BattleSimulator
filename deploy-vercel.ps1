# deploy-vercel.ps1 — one-command production deploy for the Vercel Hobby demo.
# Usage (PowerShell):  .\deploy-vercel.ps1
# Logs in only if this machine has no saved Vercel session (browser opens,
# you click Confirm), then deploys to production. See VERCEL_DEPLOY.md.
Set-Location $PSScriptRoot

$auth = Join-Path $env:LOCALAPPDATA 'com.vercel.cli\auth.json'
if (-not (Test-Path $auth)) {
    Write-Host "No Vercel session on this machine - opening login (click Confirm in the browser)..."
    npx --yes vercel login
    if ($LASTEXITCODE -ne 0) { Write-Host "Login did not complete - run the script again."; exit 1 }
}

Write-Host "Deploying to production..."
npx --yes vercel deploy --prod
if ($LASTEXITCODE -ne 0) { Write-Host "Deploy failed - see output above."; exit 1 }
Write-Host "Done. The URL above is your live site (HTML is served no-cache, so browsers always get the latest version)."
