$ErrorActionPreference = "Stop"

$script:ExitCode = 0

function Invoke-CheckedStep {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [scriptblock] $Step
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Step
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

try {
    Write-Host "Running DimooRun live e2e smoke in a real terminal."
    Write-Host "This foreground wrapper leaves output attached to this terminal and always runs cleanup."

    if (-not $env:DIMOORUN_LIVE_E2E_TIMEOUT_MS) {
        $env:DIMOORUN_LIVE_E2E_TIMEOUT_MS = "120000"
    }

    Invoke-CheckedStep "Check browser" { npm run check:e2e-browser }
    Invoke-CheckedStep "Build e2e bundle" { npm run build:e2e }
    Invoke-CheckedStep "Run live e2e smoke" { node scripts/run-live-e2e.mjs }
    Invoke-CheckedStep "Verify live e2e report" { npm run verify:e2e:live-report }
}
catch {
    if ($LASTEXITCODE -ne 0) {
        $script:ExitCode = $LASTEXITCODE
    }
    else {
        $script:ExitCode = 1
    }
    Write-Host ""
    Write-Host "Live e2e smoke failed: $($_.Exception.Message)"
}
finally {
    Write-Host ""
    Write-Host "==> Cleanup live e2e processes"
    npm run cleanup:e2e:live
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Live e2e cleanup exited with code $LASTEXITCODE"
        if ($script:ExitCode -eq 0) {
            $script:ExitCode = $LASTEXITCODE
        }
    }
}

exit $script:ExitCode
