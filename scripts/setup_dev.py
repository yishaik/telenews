#!/usr/bin/env python3
"""
Tel-Insights Development Setup Script

This script helps set up the Tel-Insights project for local development.
It handles database creation, migrations, and initial configuration.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, check=True, shell=False):
    """Run a command and handle errors."""
    print(f"Running: {command}")
    try:
        if shell:
            result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        else:
            result = subprocess.run(command.split(), check=check, capture_output=True, text=True)
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        if check:
            sys.exit(1)
        return e

def check_prerequisites():
    """Check if required tools are installed."""
    print("🔍 Checking prerequisites...")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check if PostgreSQL is available
    try:
        run_command("psql --version")
        print("✅ PostgreSQL is available")
    except:
        print("⚠️  PostgreSQL not found. Please install PostgreSQL 12+")
        print("   - Ubuntu/Debian: sudo apt install postgresql postgresql-contrib")
        print("   - macOS: brew install postgresql")
        print("   - Windows: Download from https://www.postgresql.org/download/")
    
    # Check if RabbitMQ is available
    try:
        run_command("rabbitmq-server --version", check=False)
        print("✅ RabbitMQ is available")
    except:
        print("⚠️  RabbitMQ not found. Please install RabbitMQ 3.8+")
        print("   - Ubuntu/Debian: sudo apt install rabbitmq-server")
        print("   - macOS: brew install rabbitmq")
        print("   - Windows: Download from https://www.rabbitmq.com/download.html")

def setup_environment():
    """Set up Python environment and install dependencies."""
    print("\n📦 Setting up Python environment...")
    
    # Create virtual environment if it doesn't exist
    if not os.path.exists("venv"):
        print("Creating virtual environment...")
        run_command(f"{sys.executable} -m venv venv")
    
    # Determine activation script path
    if os.name == 'nt':  # Windows
        activate_script = "venv\\Scripts\\activate"
        pip_path = "venv\\Scripts\\pip"
    else:  # Unix/Linux/macOS
        activate_script = "venv/bin/activate"
        pip_path = "venv/bin/pip"
    
    # Install dependencies
    print("Installing dependencies...")
    run_command(f"{pip_path} install --upgrade pip")
    run_command(f"{pip_path} install -r requirements.txt")
    run_command(f"{pip_path} install -e .")
    
    print(f"✅ Virtual environment created. Activate with: source {activate_script}")

def setup_environment_file():
    """Create .env file from template."""
    print("\n🔧 Setting up environment configuration...")
    
    if not os.path.exists(".env"):
        if os.path.exists("config.env.template"):
            shutil.copy("config.env.template", ".env")
            print("✅ Created .env file from template")
            print("⚠️  Please edit .env file with your actual API keys and credentials")
        else:
            print("❌ config.env.template not found")
    else:
        print("✅ .env file already exists")

def setup_database():
    """Set up PostgreSQL database."""
    print("\n🗄️  Setting up database...")
    
    # Try to create database
    try:
        run_command("createdb tel_insights", check=False)
        print("✅ Database 'tel_insights' created")
    except:
        print("ℹ️  Database might already exist or PostgreSQL not running")
    
    # Run migrations
    try:
        run_command("alembic upgrade head")
        print("✅ Database migrations applied")
    except:
        print("⚠️  Failed to run migrations. Make sure PostgreSQL is running and .env is configured")

def setup_rabbitmq():
    """Set up RabbitMQ."""
    print("\n🐰 Setting up RabbitMQ...")
    
    try:
        # Start RabbitMQ (if not running)
        if os.name == 'nt':  # Windows
            run_command("net start RabbitMQ", check=False, shell=True)
        else:  # Unix/Linux/macOS
            run_command("sudo systemctl start rabbitmq-server", check=False, shell=True)
        
        print("✅ RabbitMQ setup completed")
    except:
        print("⚠️  Could not start RabbitMQ automatically. Please start it manually:")
        print("   - Ubuntu/Debian: sudo systemctl start rabbitmq-server")
        print("   - macOS: brew services start rabbitmq")
        print("   - Windows: Start RabbitMQ service from Services panel")

def create_initial_migration():
    """Create initial database migration."""
    print("\n📝 Creating initial database migration...")
    
    try:
        run_command("alembic revision --autogenerate -m 'Initial migration'")
        print("✅ Initial migration created")
    except:
        print("⚠️  Could not create migration. Make sure alembic is configured properly")

def display_next_steps():
    """Display next steps for the user."""
    print("\n🎉 Setup completed!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your API keys and credentials:")
    print("   - TELEGRAM_API_ID and TELEGRAM_API_HASH (from https://my.telegram.org)")
    print("   - GOOGLE_API_KEY (for Gemini API)")
    print("   - TELEGRAM_BOT_TOKEN (from @BotFather)")
    print("   - Database and RabbitMQ URLs")
    
    print("\n2. Start the services:")
    print("   python -m src.aggregator.main        # Telegram message aggregator")
    print("   python -m src.ai_analysis.main       # AI analysis service")
    print("   python -m src.smart_analysis.main    # Smart analysis MCP server")
    print("   # python -m src.alerting.main        # Alerting bot (when implemented)")
    
    print("\n3. Test the setup:")
    print("   pytest tests/                        # Run tests")
    print("   curl http://localhost:8003/health    # Check Smart Analysis API")
    
    print("\n📚 Documentation:")
    print("   - README.md: Full documentation")
    print("   - TODO.md: Development progress")
    print("   - SPEC.md: Technical specifications")

def main():
    """Main setup function."""
    print("🚀 Tel-Insights Development Setup")
    print("=" * 40)
    
    # Change to project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    try:
        check_prerequisites()
        setup_environment()
        setup_environment_file()
        setup_database()
        setup_rabbitmq()
        display_next_steps()
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 