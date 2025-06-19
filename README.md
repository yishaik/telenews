# Tel-Insights: Smart Telegram News Aggregator with Advanced AI Analysis

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🎯 Project Overview

Tel-Insights is a sophisticated system that enables users to receive proactive alerts and insightful summaries from Telegram news channels, leveraging advanced analysis capabilities of large language models (LLMs). The system combats information overload, identifies hot and relevant news in real-time, and provides rich insights from every incoming message.

## 🏗️ Architecture

The project follows a **microservices architecture** with asynchronous communication through RabbitMQ:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Aggregator    │───▶│  Message Queue  │───▶│  AI Analysis    │
│   (Telethon)    │    │   (RabbitMQ)    │    │   (Gemini)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
         ▼                                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │◀───│ Smart Analysis  │───▶│    Alerting     │
│   Database      │    │   (MCP Server)  │    │ (Telegram Bot)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Modules

1. **Aggregator Module**: Connects to Telegram using Telethon, monitors channels, processes messages
2. **AI Analysis Module**: Processes messages using LLMs (Gemini 2.5 Pro) for metadata extraction
3. **Smart Analysis Module**: Implements frequency-based alerts and news summarization (MCP Server)
4. **Alerting Module**: Telegram bot for user interaction and alert delivery
5. **Data Storage Module**: PostgreSQL with JSONB support for AI metadata

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- RabbitMQ 3.8+
- Telegram API credentials
- Google Gemini API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd telenews
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp config.env.template .env
   # Edit .env with your actual credentials
   ```

4. **Set up PostgreSQL database**
   ```bash
   createdb tel_insights
   alembic upgrade head
   ```

5. **Start RabbitMQ**
   ```bash
   # On Ubuntu/Debian
   sudo systemctl start rabbitmq-server
   
   # On macOS
   brew services start rabbitmq
   
   # On Windows
   # Start RabbitMQ service from Services panel
   ```

### Configuration

Create a `.env` file based on `config.env.template`:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/tel_insights

# Message Queue
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token

# LLM API
GOOGLE_API_KEY=your_gemini_api_key

# Channels to monitor
MONITORED_CHANNELS=@channel1,@channel2,@channel3
```

## 🔧 Development Setup

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Running Services

**Using Service Runner Scripts (Recommended):**

Windows:
```cmd
run_service.bat aggregator        # Telegram message aggregator
run_service.bat ai-analysis       # AI analysis service
run_service.bat smart-analysis    # Smart analysis MCP server
run_service.bat alerting          # Telegram bot service
```

Linux/macOS:
```bash
./run_service.sh aggregator       # Telegram message aggregator
./run_service.sh ai-analysis      # AI analysis service
./run_service.sh smart-analysis   # Smart analysis MCP server
./run_service.sh alerting         # Telegram bot service
```

**Alternative - Using Python directly:**
```bash
python run_service.py aggregator
python run_service.py ai-analysis
python run_service.py smart-analysis
python run_service.py alerting
```

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m e2e

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/
isort src/

# Lint code
flake8 src/
mypy src/
```

## 📊 Features

### Phase 1 (MVP) - ✅ Completed
- [x] Telegram message aggregation from channels
- [x] Message storage with PostgreSQL
- [x] Basic AI analysis pipeline
- [x] Message queue infrastructure
- [x] Structured logging

### Phase 2 - 🔄 In Progress
- [ ] Advanced AI metadata analysis
- [ ] Frequency-based alerting
- [ ] User configuration via Telegram bot
- [ ] Media processing and analysis

### Phase 3 - ⏳ Planned
- [ ] Multimodal AI analysis (images, videos)
- [ ] Advanced analytics and trend detection
- [ ] Web management dashboard
- [ ] Real-time monitoring and metrics

## 🏛️ Database Schema

The system uses PostgreSQL with the following key tables:

- **channels**: Monitored Telegram channels
- **messages**: All collected messages with AI metadata (JSONB)
- **media**: Deduplicated media files with SHA256 hashing
- **users**: Bot users and their preferences
- **alert_configs**: User-defined alert configurations
- **prompts**: LLM prompt templates with versioning

## 🤖 AI Analysis

The AI Analysis module processes every message using:

- **Summarization**: Concise message summaries
- **Topic Classification**: Main categories and subjects
- **Sentiment Analysis**: Emotional tone analysis
- **Named Entity Recognition**: People, organizations, locations
- **Keyword Extraction**: Relevant keywords and phrases

Example AI metadata structure:
```json
{
  "summary": "Breaking news about AI development",
  "topics": ["technology", "artificial intelligence"],
  "sentiment": "positive",
  "entities": {
    "organizations": ["OpenAI", "Google"],
    "locations": ["San Francisco"]
  },
  "keywords": ["AI", "breakthrough", "development"],
  "confidence_score": 0.95
}
```

## 🚨 Smart Alerts

The Smart Analysis module provides:

- **Frequency-based alerts**: Trigger when topics appear frequently
- **Sentiment monitoring**: Alert on negative/positive sentiment spikes
- **Keyword tracking**: Monitor specific terms or phrases
- **Custom criteria**: Complex alert conditions with AND/OR logic

## 🔐 Security

- Environment-based configuration management
- Secure Telegram session handling
- Database connection pooling with proper escaping
- API authentication for internal services
- Structured logging for security monitoring

## 📈 Monitoring

- Structured logging with Rich and Structlog
- Prometheus metrics (planned)
- Health check endpoints
- Performance monitoring for LLM API usage
- Queue depth monitoring

## 🐳 Deployment

### Docker (Planned)
Each microservice will have its own Dockerfile for containerized deployment.

### Kubernetes (Planned)
Full Kubernetes manifests for production deployment with auto-scaling.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Troubleshooting

### Common Issues

**Database Connection Issues:**
```bash
# Check PostgreSQL is running
pg_isready -d tel_insights

# Reset database
dropdb tel_insights && createdb tel_insights
alembic upgrade head
```

**RabbitMQ Connection Issues:**
```bash
# Check RabbitMQ status
sudo systemctl status rabbitmq-server

# Reset RabbitMQ
sudo systemctl restart rabbitmq-server
```

**Telegram Session Issues:**
```bash
# Delete session file and re-authenticate
rm telegram_aggregator.session
python -m src.aggregator.main
```

## 📞 Support

For questions and support:
- Create an issue in the repository
- Check the [documentation](docs/)
- Review the [troubleshooting guide](#troubleshooting)

---

## 🗺️ Roadmap

- **Q1 2025**: Complete Phase 1 MVP
- **Q2 2025**: Phase 2 with advanced features
- **Q3 2025**: Phase 3 with multimodal analysis
- **Q4 2025**: Production deployment and scaling
