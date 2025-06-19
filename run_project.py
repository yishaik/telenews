#!/usr/bin/env python3
"""
Tel-Insights Project Runner

Comprehensive script to run the entire Tel-Insights project.
Handles dependency checking, environment setup, database initialization,
and orchestrates all microservices.
"""

import os
import sys
import subprocess
import asyncio
import signal
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor
import threading

# Add src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

class Colors:
    """Terminal colors for pretty output."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class ServiceManager:
    """Manages the lifecycle of Tel-Insights services."""
    
    def __init__(self):
        self.services = {
            'aggregator': {
                'module': 'aggregator.main',
                'description': 'Telegram message aggregator',
                'port': 8001,
                'dependencies': ['database', 'rabbitmq']
            },
            'ai-analysis': {
                'module': 'ai_analysis.main', 
                'description': 'AI analysis service',
                'port': 8002,
                'dependencies': ['database', 'rabbitmq', 'llm_apis']
            },
            'smart-analysis': {
                'module': 'smart_analysis.main',
                'description': 'Smart analysis MCP server',
                'port': 8003,
                'dependencies': ['database', 'llm_apis']
            },
            'alerting': {
                'module': 'alerting.main',
                'description': 'Telegram bot alerting service',
                'port': 8004,
                'dependencies': ['database', 'telegram_bot']
            }
        }
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = False
        self.shutdown_event = threading.Event()
        
    def print_banner(self):
        """Print the Tel-Insights banner."""
        banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                      TEL-INSIGHTS                            ║
║                 Project Runner v2.0                          ║
║           Telegram News Aggregation & Analysis              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}
"""
        print(banner)
    
    def check_python_version(self) -> bool:
        """Check if Python version is compatible."""
        if sys.version_info < (3, 9):
            print(f"{Colors.RED}❌ Python 3.9+ required. Current: {sys.version}{Colors.END}")
            return False
        print(f"{Colors.GREEN}✅ Python version: {sys.version.split()[0]}{Colors.END}")
        return True
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are installed."""
        print(f"{Colors.BLUE}📦 Checking dependencies...{Colors.END}")
        
        required_packages = [
            'fastapi', 'uvicorn', 'telethon', 'telegram', 'psycopg2', 
            'sqlalchemy', 'alembic', 'pika', 'google.generativeai',
            'anthropic', 'openai', 'structlog', 'rich', 'pydantic'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                print(f"  ✅ {package}")
            except ImportError:
                print(f"  ❌ {package}")
                missing_packages.append(package)
        
        if missing_packages:
            print(f"\n{Colors.RED}❌ Missing packages: {', '.join(missing_packages)}{Colors.END}")
            print(f"{Colors.YELLOW}💡 Run: pip install -r requirements.txt{Colors.END}")
            return False
        
        print(f"{Colors.GREEN}✅ All dependencies installed{Colors.END}")
        return True
    
    def check_environment(self) -> bool:
        """Check if environment configuration exists and is valid."""
        print(f"{Colors.BLUE}🔧 Checking environment configuration...{Colors.END}")
        
        env_file = project_root / ".env"
        if not env_file.exists():
            print(f"{Colors.RED}❌ .env file not found{Colors.END}")
            print(f"{Colors.YELLOW}💡 Copy config.env.template to .env and configure it{Colors.END}")
            return False
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv(env_file)
        
        required_vars = [
            'DATABASE_URL', 'TELEGRAM_API_ID', 'TELEGRAM_API_HASH',
            'TELEGRAM_BOT_TOKEN', 'RABBITMQ_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
            else:
                print(f"  ✅ {var}")
        
        if missing_vars:
            print(f"\n{Colors.RED}❌ Missing environment variables: {', '.join(missing_vars)}{Colors.END}")
            return False
        
        print(f"{Colors.GREEN}✅ Environment configuration valid{Colors.END}")
        return True
    
    def check_database(self) -> bool:
        """Check database connectivity."""
        print(f"{Colors.BLUE}🗄️  Checking database connection...{Colors.END}")
        
        try:
            from shared.database import sync_engine
            from sqlalchemy import text
            
            with sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            print(f"{Colors.GREEN}✅ Database connection successful{Colors.END}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Database connection failed: {e}{Colors.END}")
            print(f"{Colors.YELLOW}💡 Make sure PostgreSQL is running and DATABASE_URL is correct{Colors.END}")
            return False
    
    def initialize_database(self) -> bool:
        """Initialize database tables."""
        print(f"{Colors.BLUE}🏗️  Initializing database...{Colors.END}")
        
        try:
            from shared.database import init_db
            init_db()
            print(f"{Colors.GREEN}✅ Database initialized{Colors.END}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Database initialization failed: {e}{Colors.END}")
            return False
    
    def check_rabbitmq(self) -> bool:
        """Check RabbitMQ connectivity."""
        print(f"{Colors.BLUE}🐰 Checking RabbitMQ connection...{Colors.END}")
        
        try:
            import pika
            rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
            connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            connection.close()
            
            print(f"{Colors.GREEN}✅ RabbitMQ connection successful{Colors.END}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ RabbitMQ connection failed: {e}{Colors.END}")
            print(f"{Colors.YELLOW}💡 Make sure RabbitMQ is running{Colors.END}")
            return False
    
    def run_preflight_checks(self) -> bool:
        """Run all preflight checks."""
        print(f"{Colors.BOLD}🔍 Running preflight checks...{Colors.END}\n")
        
        checks = [
            self.check_python_version,
            self.check_dependencies, 
            self.check_environment,
            self.check_database,
            self.check_rabbitmq
        ]
        
        for check in checks:
            if not check():
                print(f"\n{Colors.RED}❌ Preflight checks failed!{Colors.END}")
                return False
            print()
        
        print(f"{Colors.GREEN}✅ All preflight checks passed!{Colors.END}\n")
        return True
    
    def start_service(self, service_name: str) -> bool:
        """Start a single service."""
        if service_name not in self.services:
            print(f"{Colors.RED}❌ Unknown service: {service_name}{Colors.END}")
            return False
        
        service = self.services[service_name]
        module = service['module']
        
        print(f"{Colors.BLUE}🚀 Starting {service_name} ({service['description']})...{Colors.END}")
        
        # Set up environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_path) + os.pathsep + env.get('PYTHONPATH', '')
        
        try:
            process = subprocess.Popen(
                [sys.executable, '-m', module],
                cwd=project_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            self.processes[service_name] = process
            print(f"{Colors.GREEN}✅ {service_name} started (PID: {process.pid}){Colors.END}")
            return True
            
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to start {service_name}: {e}{Colors.END}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Stop a single service."""
        if service_name not in self.processes:
            return True
        
        process = self.processes[service_name]
        if process.poll() is None:  # Process is still running
            print(f"{Colors.YELLOW}⏹️  Stopping {service_name}...{Colors.END}")
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"{Colors.RED}🔨 Force killing {service_name}...{Colors.END}")
                process.kill()
            
            print(f"{Colors.GREEN}✅ {service_name} stopped{Colors.END}")
        
        del self.processes[service_name]
        return True
    
    def monitor_services(self):
        """Monitor service health and restart if needed."""
        while self.running and not self.shutdown_event.is_set():
            for service_name, process in list(self.processes.items()):
                if process.poll() is not None:  # Process has died
                    print(f"{Colors.RED}💀 Service {service_name} died unexpectedly{Colors.END}")
                    del self.processes[service_name]
                    
                    if self.running:
                        print(f"{Colors.YELLOW}🔄 Restarting {service_name}...{Colors.END}")
                        self.start_service(service_name)
            
            time.sleep(5)  # Check every 5 seconds
    
    def start_all_services(self) -> bool:
        """Start all services in dependency order."""
        print(f"{Colors.BOLD}🚀 Starting all services...{Colors.END}\n")
        
        # Start services in order
        service_order = ['aggregator', 'ai-analysis', 'smart-analysis', 'alerting']
        
        for service_name in service_order:
            if not self.start_service(service_name):
                print(f"\n{Colors.RED}❌ Failed to start services!{Colors.END}")
                return False
            time.sleep(2)  # Give each service time to start
        
        print(f"\n{Colors.GREEN}✅ All services started successfully!{Colors.END}")
        
        # Start monitoring thread
        self.running = True
        monitor_thread = threading.Thread(target=self.monitor_services, daemon=True)
        monitor_thread.start()
        
        return True
    
    def stop_all_services(self):
        """Stop all services."""
        print(f"\n{Colors.YELLOW}⏹️  Stopping all services...{Colors.END}")
        self.running = False
        self.shutdown_event.set()
        
        # Stop services in reverse order
        service_order = ['alerting', 'smart-analysis', 'ai-analysis', 'aggregator']
        
        for service_name in service_order:
            self.stop_service(service_name)
        
        print(f"{Colors.GREEN}✅ All services stopped{Colors.END}")
    
    def show_status(self):
        """Show status of all services."""
        print(f"{Colors.BOLD}📊 Service Status:{Colors.END}\n")
        
        for service_name, service in self.services.items():
            if service_name in self.processes:
                process = self.processes[service_name]
                if process.poll() is None:
                    status = f"{Colors.GREEN}🟢 RUNNING{Colors.END}"
                    pid = f"(PID: {process.pid})"
                else:
                    status = f"{Colors.RED}🔴 DEAD{Colors.END}"
                    pid = ""
            else:
                status = f"{Colors.YELLOW}🟡 STOPPED{Colors.END}"
                pid = ""
            
            print(f"  {service_name:<15} {status} {pid}")
            print(f"    {service['description']}")
            print(f"    Port: {service['port']}")
            print()
    
    def run_interactive_mode(self):
        """Run in interactive mode with service management."""
        self.print_banner()
        
        print(f"{Colors.CYAN}📋 Interactive Mode - Available Commands:{Colors.END}")
        print("  start <service>  - Start a specific service")
        print("  stop <service>   - Stop a specific service") 
        print("  restart <service> - Restart a specific service")
        print("  status           - Show service status")
        print("  logs <service>   - Show service logs")
        print("  quit/exit        - Exit interactive mode")
        print()
        
        while True:
            try:
                command = input(f"{Colors.BOLD}tel-insights> {Colors.END}").strip().split()
                if not command:
                    continue
                
                cmd = command[0].lower()
                
                if cmd in ['quit', 'exit']:
                    break
                elif cmd == 'status':
                    self.show_status()
                elif cmd == 'start' and len(command) > 1:
                    self.start_service(command[1])
                elif cmd == 'stop' and len(command) > 1:
                    self.stop_service(command[1])
                elif cmd == 'restart' and len(command) > 1:
                    self.stop_service(command[1])
                    time.sleep(1)
                    self.start_service(command[1])
                elif cmd == 'logs' and len(command) > 1:
                    service_name = command[1]
                    if service_name in self.processes:
                        process = self.processes[service_name]
                        # This would need more sophisticated log handling
                        print(f"Logs for {service_name} (PID: {process.pid})")
                    else:
                        print(f"Service {service_name} not running")
                else:
                    print("Unknown command. Type 'quit' to exit.")
                    
            except KeyboardInterrupt:
                break
        
        self.stop_all_services()


def setup_signal_handlers(service_manager: ServiceManager):
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        print(f"\n{Colors.YELLOW}🛑 Received shutdown signal...{Colors.END}")
        service_manager.stop_all_services()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Main function."""
    service_manager = ServiceManager()
    setup_signal_handlers(service_manager)
    
    if len(sys.argv) == 1:
        # No arguments - run all services
        service_manager.print_banner()
        
        if not service_manager.run_preflight_checks():
            sys.exit(1)
        
        if not service_manager.initialize_database():
            sys.exit(1)
        
        if not service_manager.start_all_services():
            sys.exit(1)
        
        print(f"{Colors.CYAN}🎉 Tel-Insights is now running!{Colors.END}")
        print(f"{Colors.CYAN}   Press Ctrl+C to stop all services{Colors.END}\n")
        
        service_manager.show_status()
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            service_manager.stop_all_services()
    
    elif sys.argv[1] == 'interactive':
        service_manager.run_interactive_mode()
    
    elif sys.argv[1] == 'status':
        service_manager.show_status()
    
    elif sys.argv[1] in service_manager.services:
        # Run single service
        service_name = sys.argv[1]
        service_manager.print_banner()
        
        if not service_manager.run_preflight_checks():
            sys.exit(1)
        
        if not service_manager.start_service(service_name):
            sys.exit(1)
        
        print(f"{Colors.CYAN}🎉 {service_name} is now running!{Colors.END}")
        print(f"{Colors.CYAN}   Press Ctrl+C to stop{Colors.END}\n")
        
        try:
            service_manager.processes[service_name].wait()
        except KeyboardInterrupt:
            service_manager.stop_service(service_name)
    
    else:
        print("Tel-Insights Project Runner")
        print("=" * 30)
        print()
        print("Usage:")
        print("  python run_project.py                    # Run all services")
        print("  python run_project.py interactive        # Interactive mode")
        print("  python run_project.py status             # Show service status")
        print("  python run_project.py <service_name>     # Run specific service")
        print()
        print("Available services:")
        for name, service in service_manager.services.items():
            print(f"  {name:<15} - {service['description']}")
        print()
        print("Examples:")
        print("  python run_project.py aggregator")
        print("  python run_project.py interactive")


if __name__ == "__main__":
    main() 