#!/usr/bin/env python3
"""
Tel-Insights Service Runner

Helper script to run Tel-Insights services with proper Python path setup.
This fixes the import issues by ensuring the src directory is in the Python path.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def run_service(service_name: str):
    """Run a Tel-Insights service with proper environment setup."""
    
    # Set up environment
    env = os.environ.copy()
    env['PYTHONPATH'] = str(src_path) + os.pathsep + env.get('PYTHONPATH', '')
    
    # Service modules mapping
    services = {
        'aggregator': 'aggregator.main',
        'ai-analysis': 'ai_analysis.main', 
        'smart-analysis': 'smart_analysis.main',
        'alerting': 'alerting.main'
    }
    
    if service_name not in services:
        print(f"❌ Unknown service: {service_name}")
        print(f"Available services: {', '.join(services.keys())}")
        sys.exit(1)
    
    module = services[service_name]
    
    try:
        print(f"🚀 Starting {service_name} service...")
        print(f"📂 Working directory: {project_root}")
        print(f"🐍 Python path: {src_path}")
        print(f"📦 Module: {module}")
        print("-" * 50)
        
        # Run the service
        result = subprocess.run(
            [sys.executable, '-m', module],
            cwd=project_root,
            env=env
        )
        
        sys.exit(result.returncode)
        
    except KeyboardInterrupt:
        print(f"\n⏹️  {service_name} service stopped by user")
    except Exception as e:
        print(f"❌ Error running {service_name}: {e}")
        sys.exit(1)


def main():
    """Main function to parse arguments and run service."""
    if len(sys.argv) != 2:
        print("Tel-Insights Service Runner")
        print("=" * 30)
        print()
        print("Usage: python run_service.py <service_name>")
        print()
        print("Available services:")
        print("  aggregator      - Telegram message aggregator")
        print("  ai-analysis     - AI analysis service") 
        print("  smart-analysis  - Smart analysis MCP server")
        print("  alerting        - Telegram bot service")
        print()
        print("Examples:")
        print("  python run_service.py aggregator")
        print("  python run_service.py ai-analysis")
        print("  python run_service.py smart-analysis")
        print("  python run_service.py alerting")
        sys.exit(1)
    
    service_name = sys.argv[1]
    run_service(service_name)


if __name__ == "__main__":
    main() 