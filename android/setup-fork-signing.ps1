# Run once on a trusted Windows PC with JDK (keytool) and GitHub CLI (gh).
# Creates/uses a permanent private signing certificate and uploads only GitHub Actions secrets.
# Never commit the keystore or displayed password. Back them up offline.
param(
    [string]$Repo = "dissidius/peanuts-native",
    [string]$Keystore = (Join-Path $HOME ".peanuts-native\peanuts-fork-signing.p12"),
    [string]$Alias = "peanuts-native-fork"
)
$ErrorActionPreference = "Stop"
if (-not (Get-Command keytool -ErrorAction SilentlyContinue)) { throw "keytool not found. Install JDK 21, then reopen PowerShell." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI missing. Install it with: winget install --id GitHub.cli -e" }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw "Sign into GitHub CLI first: gh auth login" }
$parent = Split-Path -Parent $Keystore
New-Item -Path $parent -ItemType Directory -Force | Out-Null
if (Test-Path -LiteralPath $Keystore) {
    Write-Host "Reusing the EXISTING keystore: $Keystore"
    $secure = Read-Host "Enter the existing keystore password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    & keytool -list -keystore $Keystore -storepass $password -alias $Alias *> $null
    if ($LASTEXITCODE -ne 0) { throw "Keystore password or alias is incorrect; nothing uploaded." }
} else {
    $bytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $password = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    Write-Host ""
    Write-Host "IMPORTANT: Save this password in your password manager NOW (it is displayed only this time):"
    Write-Host $password
    Write-Host ""
    & keytool -genkeypair -noprompt -storetype PKCS12 -keystore $Keystore -alias $Alias -keyalg RSA -keysize 3072 -sigalg SHA256withRSA -validity 10000 -dname "CN=Peanuts Native Fork, O=Personal Build" -storepass $password -keypass $password
    if ($LASTEXITCODE -ne 0) { throw "Key generation failed; no secrets uploaded." }
}
# The gh CLI encrypts these as private repository Actions secrets. No private key enters git.
$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Keystore)))
$tmp = [IO.Path]::GetTempFileName()
try {
    $pairs = @("PEANUTS_SIGN_STORE_B64=$base64", "PEANUTS_SIGN_ALIAS=$Alias", "PEANUTS_SIGN_PASS=$password")
    [IO.File]::WriteAllText($tmp, ($pairs -join [Environment]::NewLine) + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
    & gh secret set -R $Repo -f $tmp
    if ($LASTEXITCODE -ne 0) { throw "GitHub secrets could not be configured. Keep the key and retry." }
} finally {
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
    $base64 = $null; $password = $null
}
Write-Host ""
Write-Host "Signing secrets configured for $Repo."
Write-Host "Back up this private keystore securely: $Keystore"
Write-Host "All future fork APK builds must reuse this exact key, alias and password."