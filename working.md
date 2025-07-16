# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Dependencies
```bash
# Install Poetry (if not already installed)
make install_poetry

# Initialize Poetry environment
make poetry_start

# Install dependencies
make poetry_install

# Update dependencies
make poetry_update
```

### Running the Application
```bash
# Start with Docker (recommended)
make build      # Build and start containers
make start      # Start existing containers
make stop       # Stop containers
make clean      # Remove all containers and images

# Run directly (for development)
cd backend && python main.py
```

The FastAPI server runs on port 8000 with auto-reload enabled.

### Testing
No specific test commands are configured in the makefile. Check if tests exist in the backend directory and run them with `python -m pytest` from the backend directory.

## Architecture Overview

### Core Structure
- **FastAPI Application**: Main server in `backend/main.py`
- **Database Layer**: MongoDB connector in `backend/db/mdb.py`
- **API Routes**: Organized in `backend/routers/`
- **Background Processing**: Scheduler and scrapers for automated data collection
- **AI/ML Components**: AWS Bedrock integration and embeddings processing

### Key Components

#### API Endpoints (`backend/routers/`)
- **Content Router** (`content.py`): Handles content suggestions, news, reddit posts, and user profiles
- **Drafts Router** (`drafts.py`): CRUD operations for draft documents with user-specific access
- **Services Router** (`services.py`): Additional service endpoints

#### Data Processing Pipeline
- **News Scraper** (`scrapers/news_scraper.py`): Collects articles from multiple news categories
- **Reddit Scraper** (`scrapers/social_listening.py`): Scrapes posts from configured subreddits
- **Embedding Processor** (`embeddings/process_embeddings.py`): Generates vector embeddings for content
- **Content Analyzer** (`bedrock/llm_output.py`): AI-powered content analysis using AWS Bedrock

#### Scheduler (`scheduler/data_scheduler.py`)
Automated daily jobs:
- News scraping at 15:45 UTC
- Reddit scraping at 15:55 UTC  
- Embedding processing at 16:03 UTC
- Content suggestion generation at 16:05 UTC
- Cleanup tasks to maintain collection limits

#### Database Collections
- `news`: News articles with embeddings
- `reddit_posts`: Reddit posts with embeddings
- `suggestions`: AI-generated content suggestions
- `drafts`: User-created draft documents
- `userProfiles`: User profile information

### Key Dependencies
- **FastAPI**: Web framework
- **MongoDB**: Database with PyMongo driver
- **AWS Bedrock**: AI/ML services (Anthropic, Cohere)
- **Embeddings**: VoyageAI for vector embeddings
- **Web Scraping**: BeautifulSoup, Requests, Firecrawl
- **Social APIs**: Tweepy (Twitter), PRAW (Reddit)
- **Scheduling**: Custom scheduler for automated tasks

### Environment Configuration
The application requires environment variables in `backend/.env`:
- `MONGODB_URI`: MongoDB connection string
- `DATABASE_NAME`: Database name
- `APP_NAME`: Application identifier
- AWS credentials for Bedrock services
- API keys for news sources and social platforms

### Docker Setup
The application uses Docker Compose with:
- Backend service built from `Dockerfile.backend`
- AWS credentials mounted as volumes
- Port 8000 exposed for API access
- Auto-restart enabled