# Tel-Insights Import Fix Guide

## 🐛 Problem: Import Errors

When trying to run the services with commands like:
```bash
python -m src.aggregator.main
python -m src.ai_analysis.main
python -m src.smart_analysis.main
```

You encounter errors like:
```
ModuleNotFoundError: No module named 'shared'
```

## 🔍 Root Cause

The issue occurs because the modules are trying to import `from shared.config import get_settings`, but Python can't find the `shared` module when running from the project root. The `shared` module is actually located at `src/shared`, but Python's module resolution doesn't automatically include the `src` directory in the path.

## ✅ Solutions

### **Option 1: Use the Service Runner Scripts (RECOMMENDED)**

We've created helper scripts that automatically set up the correct Python path:

#### **For Windows:**
```cmd
# Run individual services
run_service.bat aggregator
run_service.bat ai-analysis  
run_service.bat smart-analysis
run_service.bat alerting
```

#### **For Linux/macOS:**
```bash
# Make script executable (Linux/macOS only)
chmod +x run_service.sh

# Run individual services
./run_service.sh aggregator
./run_service.sh ai-analysis
./run_service.sh smart-analysis
./run_service.sh alerting
```

#### **Using Python directly:**
```bash
python run_service.py aggregator
python run_service.py ai-analysis
python run_service.py smart-analysis
python run_service.py alerting
```

### **Option 2: Set PYTHONPATH Environment Variable**

#### **Windows (PowerShell):**
```powershell
$env:PYTHONPATH = "$(pwd)\src;$env:PYTHONPATH"
python -m aggregator.main
python -m ai_analysis.main
python -m smart_analysis.main
python -m alerting.main
```

#### **Windows (Command Prompt):**
```cmd
set PYTHONPATH=%cd%\src;%PYTHONPATH%
python -m aggregator.main
python -m ai_analysis.main
python -m smart_analysis.main
python -m alerting.main
```

#### **Linux/macOS:**
```bash
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
python -m aggregator.main
python -m ai_analysis.main
python -m smart_analysis.main
python -m alerting.main
```

### **Option 3: Run from src Directory**

```bash
cd src
python -m aggregator.main
python -m ai_analysis.main
python -m smart_analysis.main
python -m alerting.main
```

### **Option 4: Install in Development Mode**

```bash
pip install -e .
```

Then run using entry points (if configured in setup.py):
```bash
tel-insights-aggregator
tel-insights-ai-analysis
tel-insights-smart-analysis
tel-insights-alerting
```

## 🚀 Complete Startup Sequence

Here's how to start all services in the correct order:

### **Terminal 1: Aggregator Service**
```bash
# Windows
run_service.bat aggregator

# Linux/macOS
./run_service.sh aggregator
```

### **Terminal 2: AI Analysis Service**
```bash
# Windows
run_service.bat ai-analysis

# Linux/macOS
./run_service.sh ai-analysis
```

### **Terminal 3: Smart Analysis Service**
```bash
# Windows
run_service.bat smart-analysis

# Linux/macOS
./run_service.sh smart-analysis
```

### **Terminal 4: Alerting Service (Optional)**
```bash
# Windows
run_service.bat alerting

# Linux/macOS
./run_service.sh alerting
```

## 🔧 Troubleshooting

### **1. Python Path Issues**
If you still get import errors:
- Ensure you're in the project root directory (`telenews`)
- Check that the `src` directory exists and contains the modules
- Verify your Python version is 3.9+

### **2. Missing Dependencies**
```bash
pip install -r requirements.txt
```

### **3. Database Connection Issues**
- Ensure PostgreSQL is running
- Check your `.env` file has correct database credentials
- Run database migrations: `alembic upgrade head`

### **4. RabbitMQ Connection Issues**
- Ensure RabbitMQ is running
- Check RabbitMQ management interface: http://localhost:15672
- Default credentials: guest/guest

### **5. API Key Issues**
Ensure your `.env` file contains:
```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
GOOGLE_API_KEY=your_gemini_api_key
```

## 📊 Verify Services are Running

### **Check Service Health:**
```bash
# Smart Analysis API
curl http://localhost:8003/health

# Check if services are running
ps aux | grep python  # Linux/macOS
tasklist | findstr python  # Windows
```

### **Check Logs:**
Services will output logs to the console. Look for:
- ✅ "Service initialized successfully"
- ✅ "Starting [Service] Service..."
- ❌ Any error messages

## 🎯 Expected Output

When services start correctly, you should see:

**Aggregator Service:**
```
🚀 Starting aggregator service...
📂 Working directory: C:\Users\...\telenews
🐍 Python path includes: C:\Users\...\telenews\src
📦 Module: aggregator.main
--------------------------------------------------
[INFO] Aggregator Service initialized successfully
[INFO] Starting Aggregator Service...
```

**AI Analysis Service:**
```
🚀 Starting ai-analysis service...
[INFO] AI Analysis Service initialized successfully
[INFO] Starting AI Analysis Service...
```

**Smart Analysis Service:**
```
🚀 Starting smart-analysis service...
[INFO] Smart Analysis Service initialized successfully
[INFO] Starting Smart Analysis Service...
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8003
```

## 📚 Next Steps

Once all services are running:

1. **Test the API:**
   ```bash
   curl http://localhost:8003/health
   ```

2. **Check database:**
   ```sql
   SELECT COUNT(*) FROM messages;
   ```

3. **Monitor logs for message processing**

4. **Set up alert configurations via Telegram bot**

## 🆘 Still Having Issues?

If you're still encountering problems:

1. Check you have all prerequisites installed (Python 3.9+, PostgreSQL, RabbitMQ)
2. Verify your `.env` file is properly configured
3. Ensure all dependencies are installed: `pip install -r requirements.txt`
4. Try running the automated setup: `python scripts/setup_dev.py`
5. Check the troubleshooting section in [DEVELOPMENT.md](DEVELOPMENT.md)

---

## 🎉 Success!

Once you see all services running without errors, your Tel-Insights system is ready! The services will:

- **Aggregator**: Monitor Telegram channels and collect messages
- **AI Analysis**: Process messages with Google Gemini for metadata extraction  
- **Smart Analysis**: Provide news summarization and alert checking
- **Alerting**: Handle user interactions via Telegram bot

Happy news aggregating! 📰🤖 