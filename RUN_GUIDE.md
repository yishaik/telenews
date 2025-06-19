# Tel-Insights Project - Run Guide

This guide explains how to run the Tel-Insights project using the various run scripts provided.

## 🚀 Quick Start

The easiest way to run the entire project:

### On Windows (PowerShell)
```powershell
.\run_project.ps1
```

### On Linux/Mac (Bash)
```bash
./run_project.sh
```

### Cross-platform (Python)
```bash
python run_project.py
```

## 📋 Prerequisites

Before running the project, ensure you have:

1. **Python 3.9+** installed
2. **PostgreSQL** database running
3. **RabbitMQ** message broker running
4. **Environment configuration** (`.env` file)

## 🔧 Setup Instructions

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd telenews

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy template and edit configuration
cp config.env.template .env
# Edit .env file with your settings
```

### 3. Setup External Services

#### PostgreSQL Database
```bash
# Create database
createdb tel_insights

# Update DATABASE_URL in .env file
DATABASE_URL=postgresql://username:password@localhost:5432/tel_insights
```

#### RabbitMQ Message Broker
```bash
# Install and start RabbitMQ
# Ubuntu/Debian:
sudo apt-get install rabbitmq-server
sudo systemctl start rabbitmq-server

# Or using Docker:
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

## 🎯 Running Services

### Option 1: All Services (Recommended)

Run all services together with automatic dependency management:

```bash
# Python runner (cross-platform)
python run_project.py

# Shell script (Linux/Mac)
./run_project.sh

# PowerShell (Windows)
.\run_project.ps1
```

### Option 2: Individual Services

Run specific services independently:

```bash
# Using Python runner
python run_project.py aggregator
python run_project.py ai-analysis
python run_project.py smart-analysis
python run_project.py alerting

# Using shell script
./run_project.sh aggregator
./run_project.sh ai-analysis
./run_project.sh smart-analysis
./run_project.sh alerting

# Using PowerShell
.\run_project.ps1 -Service aggregator
.\run_project.ps1 -Service ai-analysis
.\run_project.ps1 -Service smart-analysis
.\run_project.ps1 -Service alerting
```

### Option 3: Legacy Single Service Runner

Use the original service runner for individual services:

```bash
python run_service.py <service_name>
```

## 🛠️ Available Run Scripts

### 1. `run_project.py` - Main Python Runner

**Features:**
- Cross-platform compatibility
- Comprehensive preflight checks
- Automatic dependency validation
- Service health monitoring
- Interactive mode
- Colored output
- Signal handling for graceful shutdown

**Usage:**
```bash
python run_project.py                    # Run all services
python run_project.py interactive        # Interactive mode
python run_project.py status             # Show service status
python run_project.py <service_name>     # Run specific service
```

**Interactive Mode Commands:**
- `start <service>` - Start a specific service
- `stop <service>` - Stop a specific service
- `restart <service>` - Restart a specific service
- `status` - Show service status
- `quit/exit` - Exit interactive mode

### 2. `run_project.sh` - Shell Script (Linux/Mac)

**Features:**
- Fast startup for Unix systems
- Parallel service execution
- Virtual environment auto-detection
- Dependency checking
- Signal handling

**Usage:**
```bash
./run_project.sh                # Run all services
./run_project.sh <service>      # Run specific service
./run_project.sh check          # Run checks only
./run_project.sh init           # Initialize database only
```

### 3. `run_project.ps1` - PowerShell Script (Windows)

**Features:**
- Native Windows PowerShell support
- Background job management
- Colored output
- Error handling
- Virtual environment support

**Usage:**
```powershell
.\run_project.ps1                    # Run all services
.\run_project.ps1 -Service <name>    # Run specific service
.\run_project.ps1 -Check             # Run checks only
.\run_project.ps1 -Init              # Initialize database only
.\run_project.ps1 -Help              # Show help
```

## 🏗️ Service Architecture

The Tel-Insights project consists of four main services:

### 1. Aggregator Service (`aggregator`)
- **Purpose:** Telegram message aggregation
- **Port:** 8001
- **Dependencies:** Database, RabbitMQ
- **Function:** Monitors Telegram channels and collects messages

### 2. AI Analysis Service (`ai-analysis`)
- **Purpose:** AI-powered message analysis
- **Port:** 8002
- **Dependencies:** Database, RabbitMQ, LLM APIs
- **Function:** Processes messages using various AI models

### 3. Smart Analysis Service (`smart-analysis`)
- **Purpose:** MCP-based intelligent analysis
- **Port:** 8003
- **Dependencies:** Database, LLM APIs
- **Function:** Provides advanced analysis capabilities

### 4. Alerting Service (`alerting`)
- **Purpose:** Telegram bot for alerts and notifications
- **Port:** 8004
- **Dependencies:** Database, Telegram Bot API
- **Function:** Sends alerts and handles user interactions

## 🔍 Troubleshooting

### Common Issues

#### 1. Python Import Errors
```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Or use the run scripts which handle this automatically
python run_project.py <service>
```

#### 2. Database Connection Issues
- Verify PostgreSQL is running
- Check DATABASE_URL in .env file
- Ensure database exists and user has permissions

#### 3. RabbitMQ Connection Issues
- Verify RabbitMQ is running: `sudo systemctl status rabbitmq-server`
- Check RABBITMQ_URL in .env file
- Default URL: `amqp://guest:guest@localhost:5672/`

#### 4. Missing Dependencies
```bash
# Check what's missing
python run_project.py

# Install missing packages
pip install -r requirements.txt
```

#### 5. Environment Configuration
```bash
# Validate environment
python run_project.py status

# Check specific configuration
cat .env
```

### Debug Mode

Enable debug mode for more detailed logging:

1. Edit `.env` file:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

2. Or set environment variables:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

## 📊 Monitoring

### Service Status

Check service status using:

```bash
# Python runner
python run_project.py status

# Or check individual services
curl http://localhost:8001/health  # Aggregator
curl http://localhost:8002/health  # AI Analysis
curl http://localhost:8003/health  # Smart Analysis
curl http://localhost:8004/health  # Alerting
```

### Logs

Service logs are output to stdout. For persistent logging:

```bash
# Redirect logs to files
python run_project.py > tel_insights.log 2>&1

# Or use systemd for production
sudo systemctl status tel-insights
```

## 🚀 Production Deployment

For production deployment, consider:

1. **Use systemd services** (Linux)
2. **Setup log rotation**
3. **Configure reverse proxy** (nginx/Apache)
4. **Use environment-specific .env files**
5. **Setup monitoring** (Prometheus/Grafana)
6. **Configure backups** for database

### Example Systemd Service

Create `/etc/systemd/system/tel-insights.service`:

```ini
[Unit]
Description=Tel-Insights Project
After=network.target postgresql.service rabbitmq-server.service

[Service]
Type=simple
User=tel-insights
WorkingDirectory=/opt/tel-insights
ExecStart=/opt/tel-insights/venv/bin/python run_project.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable tel-insights
sudo systemctl start tel-insights
```

## 📞 Support

If you encounter issues:

1. Check this guide thoroughly
2. Verify all prerequisites are met
3. Check service logs for error messages
4. Ensure all environment variables are configured
5. Validate external services (PostgreSQL, RabbitMQ) are running

For development issues, refer to `DEVELOPMENT.md` for detailed development setup instructions. 