# Tel-Insights Project Runner (PowerShell Version)
# PowerShell script to run the Tel-Insights project services on Windows

param(
    [string]$Service = "",
    [switch]$Check,
    [switch]$Init,
    [switch]$Help
)

# Set strict mode for better error handling
Set-StrictMode -Version Latest

# Project paths
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SrcPath = Join-Path $ProjectRoot "src"

# Color functions for pretty output
function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️ $Message" -ForegroundColor Blue
}

function Write-Banner {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                      TEL-INSIGHTS                            ║" -ForegroundColor Cyan
    Write-Host "║                 Project Runner v2.0                          ║" -ForegroundColor Cyan
    Write-Host "║           Telegram News Aggregation & Analysis              ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

# Check Python installation
function Test-Python {
    try {
        $pythonVersion = python --version 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Python not found"
        }
        
        $version = [version]($pythonVersion -replace "Python ", "")
        if ($version -lt [version]"3.9") {
            Write-Error "Python 3.9+ required. Current: $pythonVersion"
            return $false
        }
        
        Write-Success "Python version: $pythonVersion"
        return $true
    }
    catch {
        Write-Error "Python 3 is not installed or not in PATH"
        return $false
    }
}

# Check virtual environment
function Test-VirtualEnvironment {
    $venvPath = Join-Path $ProjectRoot "venv"
    if (Test-Path $venvPath) {
        Write-Info "Virtual environment found at: $venvPath"
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        if (Test-Path $activateScript) {
            Write-Info "Activating virtual environment..."
            & $activateScript
            Write-Success "Virtual environment activated"
        }
    }
    else {
        Write-Warning "Virtual environment not found. Using system Python."
        Write-Info "Consider creating one with: python -m venv venv"
    }
}

# Check environment configuration
function Test-Environment {
    $envFile = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path $envFile)) {
        Write-Error ".env file not found"
        Write-Warning "Copy config.env.template to .env and configure it"
        return $false
    }
    Write-Success "Environment configuration found"
    return $true
}

# Check Python dependencies
function Test-Dependencies {
    $requirementsFile = Join-Path $ProjectRoot "requirements.txt"
    if (Test-Path $requirementsFile) {
        Write-Info "Checking Python dependencies..."
        
        try {
            $checkScript = @"
import pkg_resources
import sys

def check_requirements():
    with open('$($requirementsFile.Replace('\', '\\'))', 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    missing = []
    for req in requirements:
        try:
            pkg_resources.require(req)
        except:
            missing.append(req.split('==')[0])
    
    if missing:
        print('Missing packages:', ', '.join(missing))
        sys.exit(1)
    else:
        print('All dependencies satisfied')

check_requirements()
"@
            
            $result = python -c $checkScript
            if ($LASTEXITCODE -eq 0) {
                Write-Success "All Python dependencies are installed"
                return $true
            }
            else {
                Write-Error "Some dependencies are missing: $result"
                Write-Info "Install with: pip install -r requirements.txt"
                return $false
            }
        }
        catch {
            Write-Error "Failed to check dependencies"
            return $false
        }
    }
    return $true
}

# Initialize database
function Initialize-Database {
    Write-Info "Initializing database..."
    
    $env:PYTHONPATH = "$SrcPath;$env:PYTHONPATH"
    Set-Location $ProjectRoot
    
    try {
        $initScript = @"
from src.shared.database import init_db
try:
    init_db()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    exit(1)
"@
        
        $result = python -c $initScript
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Database initialized"
            return $true
        }
        else {
            Write-Error "Database initialization failed: $result"
            return $false
        }
    }
    catch {
        Write-Error "Database initialization failed: $_"
        return $false
    }
}

# Run a single service
function Start-Service {
    param([string]$ServiceName)
    
    $modules = @{
        'aggregator' = 'aggregator.main'
        'ai-analysis' = 'ai_analysis.main'
        'smart-analysis' = 'smart_analysis.main'
        'alerting' = 'alerting.main'
    }
    
    if (-not $modules.ContainsKey($ServiceName)) {
        Write-Error "Unknown service: $ServiceName"
        Write-Host "Available services: $($modules.Keys -join ', ')"
        return $false
    }
    
    $module = $modules[$ServiceName]
    Write-Info "Starting $ServiceName service..."
    
    $env:PYTHONPATH = "$SrcPath;$env:PYTHONPATH"
    Set-Location $ProjectRoot
    
    try {
        python -m $module
    }
    catch {
        Write-Error "Failed to start service $ServiceName`: $_"
        return $false
    }
}

# Run all services
function Start-AllServices {
    Write-Info "Starting all services..."
    
    $services = @('aggregator', 'ai-analysis', 'smart-analysis', 'alerting')
    $jobs = @()
    
    foreach ($service in $services) {
        Write-Info "Starting $service..."
        
        $scriptBlock = {
            param($service, $projectRoot, $srcPath)
            
            $modules = @{
                'aggregator' = 'aggregator.main'
                'ai-analysis' = 'ai_analysis.main'
                'smart-analysis' = 'smart_analysis.main'
                'alerting' = 'alerting.main'
            }
            
            $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH"
            Set-Location $projectRoot
            python -m $modules[$service]
        }
        
        $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList $service, $ProjectRoot, $SrcPath
        $jobs += $job
        
        Start-Sleep -Seconds 2
    }
    
    Write-Success "All services started!"
    Write-Info "Job IDs: $($jobs.Id -join ', ')"
    Write-Warning "Press Ctrl+C to stop all services"
    
    try {
        # Wait for user interrupt
        while ($true) {
            Start-Sleep -Seconds 1
            
            # Check if any jobs have failed
            $failedJobs = $jobs | Where-Object { $_.State -eq 'Failed' }
            if ($failedJobs) {
                Write-Warning "Some services have failed:"
                foreach ($job in $failedJobs) {
                    Write-Error "Job $($job.Id) failed"
                    Receive-Job -Job $job
                }
            }
        }
    }
    finally {
        Write-Warning "Stopping all services..."
        $jobs | Stop-Job
        $jobs | Remove-Job -Force
        Write-Success "All services stopped"
    }
}

# Run preflight checks
function Test-Prerequisites {
    Write-Info "Running preflight checks..."
    Write-Host ""
    
    $checks = @(
        { Test-Python },
        { Test-Environment },
        { Test-Dependencies }
    )
    
    foreach ($check in $checks) {
        if (-not (& $check)) {
            Write-Error "Preflight checks failed!"
            return $false
        }
    }
    
    Write-Host ""
    Write-Success "All checks passed!"
    return $true
}

# Show usage information
function Show-Usage {
    Write-Host "Tel-Insights Project Runner (PowerShell)"
    Write-Host "========================================"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\run_project.ps1                    # Run all services"
    Write-Host "  .\run_project.ps1 -Service <name>    # Run specific service"
    Write-Host "  .\run_project.ps1 -Check             # Run checks only"
    Write-Host "  .\run_project.ps1 -Init              # Initialize database only"
    Write-Host "  .\run_project.ps1 -Help              # Show this help"
    Write-Host ""
    Write-Host "Available services:"
    Write-Host "  aggregator      - Telegram message aggregator"
    Write-Host "  ai-analysis     - AI analysis service"
    Write-Host "  smart-analysis  - Smart analysis MCP server"
    Write-Host "  alerting        - Telegram bot service"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\run_project.ps1"
    Write-Host "  .\run_project.ps1 -Service aggregator"
    Write-Host "  .\run_project.ps1 -Check"
}

# Main script logic
function Main {
    Write-Banner
    
    if ($Help) {
        Show-Usage
        return
    }
    
    if ($Check) {
        Test-Prerequisites
        return
    }
    
    if ($Init) {
        if (Test-Prerequisites) {
            Initialize-Database
        }
        return
    }
    
    if ($Service) {
        if (Test-Prerequisites) {
            Test-VirtualEnvironment
            if (Initialize-Database) {
                Start-Service -ServiceName $Service
            }
        }
        return
    }
    
    # Default: run all services
    if (Test-Prerequisites) {
        Test-VirtualEnvironment
        if (Initialize-Database) {
            Start-AllServices
        }
    }
}

# Handle Ctrl+C gracefully
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -SupportEvent -Action {
    Write-Host "`nShutting down gracefully..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job -Force
}

# Run main function
try {
    Main
}
catch {
    Write-Error "An error occurred: $_"
    exit 1
} 