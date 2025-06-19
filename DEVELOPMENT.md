# Tel-Insights Development Guide

## 🚀 Quick Start for Developers

This guide will help you set up Tel-Insights for local development and testing.

## 📋 Prerequisites

Before getting started, ensure you have the following installed:

- **Python 3.9+** 
- **PostgreSQL 12+** 
- **RabbitMQ 3.8+**
- **Git**

### Getting API Keys

You'll need the following API keys:

1. **Telegram API credentials**: Get from https://my.telegram.org
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`

2. **Telegram Bot Token**: Create a bot with @BotFather on Telegram
   - `TELEGRAM_BOT_TOKEN`

3. **Google Gemini API Key**: Get from Google AI Studio
   - `GOOGLE_API_KEY`

## 🛠️ Setup Steps

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd telenews

# Run the automated setup script
python scripts/setup_dev.py
```

The setup script will:
- Create a Python virtual environment
- Install all dependencies
- Create `.env` file from template
- Set up PostgreSQL database
- Configure RabbitMQ
- Run database migrations

### 2. Configure Environment

Edit the `.env` file with your actual credentials:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/tel_insights

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Telegram API
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_BOT_TOKEN=your_bot_token_here

# LLM API
GOOGLE_API_KEY=your_gemini_api_key

# Channels to monitor (comma-separated)
MONITORED_CHANNELS=@channel1,@channel2,@channel3
```

### 3. Initialize Database

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Run migrations
alembic upgrade head
```

## 🏃‍♂️ Running the Services

The Tel-Insights system consists of multiple microservices. Start them in separate terminals:

### Terminal 1: Aggregator Service
```bash
python -m src.aggregator.main
```
- Connects to Telegram
- Monitors specified channels
- Processes incoming messages
- Publishes events to message queue

### Terminal 2: AI Analysis Service
```bash
python -m src.ai_analysis.main
```
- Consumes messages from queue
- Processes with Google Gemini
- Stores AI metadata in database

### Terminal 3: Smart Analysis Service (MCP Server)
```bash
python -m src.smart_analysis.main
```
- Runs MCP server on `http://localhost:8003`
- Provides news summarization tools
- Implements frequency-based alerts
- Periodic alert checking

### Terminal 4: Monitor Services
```bash
# Check service health
curl http://localhost:8003/health

# View logs
tail -f logs/aggregator.log
tail -f logs/ai_analysis.log
tail -f logs/smart_analysis.log
```

## 🧪 Testing the System

### 1. Unit Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit
pytest -m integration

# Run with coverage
pytest --cov=src --cov-report=html
```

### 2. Integration Testing

1. **Send Test Message**: Send a message to one of your monitored channels
2. **Check Database**: Verify message appears in database with AI metadata
3. **Test MCP API**: Use the Smart Analysis endpoints

```bash
# Test news summarization
curl -X POST http://localhost:8003/tools/summarize_news \
  -H "Content-Type: application/json" \
  -d '{"time_range_hours": 1}'

# Test topic trends
curl -X POST http://localhost:8003/tools/topic_trends \
  -H "Content-Type: application/json" \
  -d '{"time_range_hours": 24}'

# Check alerts
curl -X POST http://localhost:8003/tools/check_alerts \
  -H "Content-Type: application/json" \
  -d '{"force_check": true}'
```

## 🛠️ Development Workflow

### Code Organization

```
src/
├── shared/           # Shared utilities and models
│   ├── config.py     # Configuration management
│   ├── database.py   # Database connections
│   ├── models.py     # SQLAlchemy models
│   ├── logging.py    # Structured logging
│   └── messaging.py  # RabbitMQ utilities
├── aggregator/       # Telegram message aggregator
├── ai_analysis/      # AI processing service
├── smart_analysis/   # MCP server and alerts
└── alerting/         # Telegram bot (TODO)

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests
└── e2e/            # End-to-end tests
```

### Code Quality

```bash
# Format code
black src/
isort src/

# Lint code
flake8 src/
mypy src/

# Run pre-commit hooks
pre-commit run --all-files
```

### Database Management

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Check migration status
alembic current
alembic history
```

## 🔍 Debugging

### Common Issues

1. **Database Connection Error**
   ```bash
   # Check PostgreSQL status
   sudo systemctl status postgresql
   
   # Check database exists
   psql -l | grep tel_insights
   ```

2. **RabbitMQ Connection Error**
   ```bash
   # Check RabbitMQ status
   sudo systemctl status rabbitmq-server
   
   # Check RabbitMQ management
   http://localhost:15672 (guest/guest)
   ```

3. **Telegram API Error**
   - Verify API credentials in `.env`
   - Check if session file exists and is valid
   - Ensure channels are accessible

4. **Gemini API Error**
   - Verify API key in `.env`
   - Check API quota and billing
   - Monitor rate limits

### Logging

Logs are structured using Structlog with different levels:

```bash
# View service logs
tail -f logs/aggregator.log
tail -f logs/ai_analysis.log
tail -f logs/smart_analysis.log

# Set debug logging
export LOG_LEVEL=DEBUG
```

## 📊 Monitoring

### Database Queries

```sql
-- Check message processing
SELECT 
    COUNT(*) as total_messages,
    COUNT(ai_metadata) as processed_messages,
    AVG(CASE WHEN ai_metadata IS NOT NULL THEN 1 ELSE 0 END) * 100 as processing_rate
FROM messages 
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Check topic trends
SELECT 
    jsonb_array_elements_text(ai_metadata->'topics') as topic,
    COUNT(*) as count
FROM messages 
WHERE ai_metadata IS NOT NULL 
    AND message_timestamp > NOW() - INTERVAL '24 hours'
GROUP BY topic 
ORDER BY count DESC 
LIMIT 10;

-- Check alert configurations
SELECT 
    u.username,
    ac.config_name,
    ac.criteria,
    ac.is_active
FROM alert_configs ac
JOIN users u ON ac.user_id = u.telegram_user_id
WHERE ac.is_active = true;
```

### Performance Monitoring

```bash
# Check queue depth
rabbitmqctl list_queues

# Monitor database connections
SELECT * FROM pg_stat_activity WHERE datname = 'tel_insights';

# Check service memory usage
ps aux | grep python | grep tel-insights
```

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
DEBUG=false

# Processing
DEFAULT_ALERT_THRESHOLD=20        # Alert trigger threshold
DEFAULT_ALERT_WINDOW_MINUTES=60   # Alert time window
ALERT_COOLDOWN_MINUTES=30         # Alert cooldown period

# LLM Settings
LLM_MAX_RETRIES=3                 # Max retry attempts
LLM_TIMEOUT_SECONDS=60            # Request timeout
DEFAULT_LLM_MODEL=gemini-1.5-pro  # Default model
```

### Channel Configuration

Add channels to monitor in `.env`:

```env
MONITORED_CHANNELS=@technews,@breakingnews,@worldnews
```

## 🚀 Deployment

### Local Development
- All services run locally
- SQLite/PostgreSQL for database
- Local RabbitMQ instance
- File-based logging

### Docker Deployment (TODO)
```bash
# Build containers
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Production Deployment (TODO)
- Kubernetes manifests in `/k8s/`
- Cloud database (Google Cloud SQL)
- Cloud message queue (Google Pub/Sub)
- Cloud storage (Google Cloud Storage)
- Monitoring with Prometheus/Grafana

## 📚 API Documentation

### Smart Analysis MCP Server

**Base URL**: `http://localhost:8003`

#### Endpoints

- `GET /` - Service information
- `GET /health` - Health check
- `POST /tools/summarize_news` - News summarization
- `POST /tools/topic_trends` - Topic trend analysis  
- `POST /tools/check_alerts` - Alert checking

#### Example Usage

```python
import requests

# Summarize last hour's news
response = requests.post(
    "http://localhost:8003/tools/summarize_news",
    json={
        "time_range_hours": 1,
        "topics": ["technology", "AI"],
        "max_messages": 50
    }
)
print(response.json())
```

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Write** tests for your changes
4. **Ensure** all tests pass (`pytest`)
5. **Format** code (`black src/`, `isort src/`)
6. **Commit** changes (`git commit -m 'Add amazing feature'`)
7. **Push** to branch (`git push origin feature/amazing-feature`)
8. **Open** a Pull Request

### Development Guidelines

- Write comprehensive tests
- Follow PEP 8 style guidelines
- Use type hints
- Add docstrings to functions
- Update documentation as needed
- Follow commit message conventions

## 📞 Support

For development questions:

- Check the [troubleshooting section](README.md#troubleshooting)
- Review existing [GitHub issues](link-to-issues)
- Create a new issue for bugs or feature requests
- Join the development discussion

## 🗺️ What's Next?

Current development priorities:

1. **Module 5: Alerting Bot** - Telegram bot for user interaction
2. **Enhanced Testing** - Comprehensive test coverage
3. **Docker Deployment** - Containerized services
4. **Web Dashboard** - Management interface
5. **Multi-modal Analysis** - Image and video processing

See [TODO.md](TODO.md) for complete development roadmap. 