#requires -Version 5.1
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)][string[]]$Files
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
& node (Join-Path $PSScriptRoot '..\release-policy.js')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($env:SKIP_WIN_CODESIGN -eq '1') { Write-Host 'SKIP_WIN_CODESIGN=1; skipping Authenticode verification.'; exit 0 }
if ($env:OS -ne 'Windows_NT') { throw 'Authenticode verification must run on Windows.' }
if ([string]::IsNullOrWhiteSpace($env:AZURE_ARTIFACT_SIGNING_PUBLISHER)) { throw 'AZURE_ARTIFACT_SIGNING_PUBLISHER is required for Authenticode verification.' }
if ([string]::IsNullOrWhiteSpace($env:AZURE_ARTIFACT_SIGNING_PUBLISHER_DN)) { throw 'AZURE_ARTIFACT_SIGNING_PUBLISHER_DN is required for full Authenticode identity verification.' }
. (Join-Path $PSScriptRoot 'artifact-signing-tools.ps1')
Import-BundledPowerShellSecurityModule

$items = @(foreach ($f in $Files) {
  if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { throw "File to verify not found: $f" }
  Get-Item -LiteralPath $f
})
if (-not $items.Count) { throw 'No Windows artifacts to verify.' }
$expected = $env:AZURE_ARTIFACT_SIGNING_PUBLISHER.Trim()
$expectedSubject = $env:AZURE_ARTIFACT_SIGNING_PUBLISHER_DN.Trim()
foreach ($file in $items) {
  $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
  if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "Invalid or missing Authenticode signature: $($file.FullName) ($($signature.Status))"
  }
  if (-not $signature.SignerCertificate) { throw "Missing signer certificate: $($file.FullName)" }
  $publisher = $signature.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
  if ($publisher -ne $expected) { throw "Unexpected publisher for $($file.FullName): '$publisher'" }
  $subject = $signature.SignerCertificate.Subject.Trim()
  if ($subject -ne $expectedSubject) { throw "Unexpected certificate Subject for $($file.FullName). Expected '$expectedSubject', got '$subject'." }
  if (-not $signature.TimeStamperCertificate) { throw "Missing RFC3161 timestamp: $($file.FullName)" }
  Write-Host "Verified: $($file.FullName)"
}
Write-Host "Verified $($items.Count) timestamped Windows artifact(s) from '$expectedSubject'."
