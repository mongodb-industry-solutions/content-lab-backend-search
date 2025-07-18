# **Content Lab - Automated Content Analysis & Suggestion Engine**

This repository hosts the backend for the ContentLab - Automated Content Analysis & Suggestion Engine service. The service uses FastAPI to deliver smart content insights, including semantic search, automated content aggregation, and AI-generated insights. It uses MongoDB for scalable storage and vector search, with scheduled jobs for continuous data ingestion and analysis. Designed for content creators and analysts, it transforms raw news and social media data into actionable, searchable intelligence.

## High Level Architecture

[High level architecture diagram here use [google slides](https://docs.google.com/presentation/d/1vo8Y8mBrocJtzvZc_tkVHZTsVW_jGueyUl-BExmVUtI/edit#slide=id.g30c066974c7_0_3536)]

## Architecture Overview

This backend is designed as a microservice, focusing on automated content analysis, aggregation, and AI-powered suggestions. Each component is modular, enabling independent scaling, maintenance, and integration with other services.

### Core Structure

- **FastAPI Application:**  
  The main entry point (`backend/main.py`) serves as the API gateway for all backend operations. It exposes REST endpoints for content retrieval, semantic search, user management, and AI-driven insights. FastAPI ensures high performance, automatic documentation, and easy integration with other microservices.

- **Database Layer:**  
  The MongoDB connector (`backend/db/mdb.py`) abstracts all database interactions. It manages connections, queries, and CRUD operations for collections such as `news`, `reddit_posts`, `suggestions`, `drafts`, and `userProfiles`. This layer ensures data consistency and scalability, supporting high-throughput ingestion and retrieval.

- **API Routes:**  
  Modular routers in `backend/routers/` separate concerns for different functionalities. Each router handles specific endpoints, making the codebase maintainable and extensible. This structure supports microservice best practices by isolating business logic.

- **Background Processing:**  
  Automated data collection is handled by schedulers and scrapers. These run as background jobs, ingesting news and social media data at scheduled intervals. This ensures the microservice remains up-to-date with the latest content without manual intervention.

- **AI/ML Components:**  
  Integration with AWS Bedrock enables advanced AI capabilities, such as semantic embeddings and content analysis. These components process raw data into actionable intelligence, supporting features like semantic search and automated suggestions.


## Key Features

## Tech Stack

### Web Framework & API
- [**fastapi**](https://fastapi.tiangolo.com/) for API development and building REST endpoints.
- [**uvicorn**](https://www.uvicorn.org/) for running the ASGI server.

### Database & Data Storage
- [**pymongo**](https://pymongo.readthedocs.io/) for MongoDB connectivity and operations.

### AWS & Cloud Services
- [**boto3**](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) for AWS SDK integration and Bedrock API access.
- [**botocore**](https://botocore.amazonaws.com/v1/documentation/api/latest/index.html) for low-level AWS service operations.
- [**cohere from Bedrock**](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-embed.html) for generating vector embeddings.

### Web Scraping & HTTP
- [**requests**](https://requests.readthedocs.io/) for HTTP requests and API calls.
- [**beautifulsoup4**](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) for HTML parsing and web scraping.

### Social Media APIs
- [**tweepy**](https://docs.tweepy.org/) for Twitter API integration.
- [**praw**](https://praw.readthedocs.io/) for Reddit API integration.

### Search & Information Retrieval
- [**langchain-community**](https://python.langchain.com/docs/integrations/providers/) for additional LangChain tools and integrations.
- [**langchain-tavily**](https://python.langchain.com/docs/integrations/tools/tavily_search/) for Tavily search integration with LangChain.

### Scheduling & Task Management
- [**scheduler**](https://schedule.readthedocs.io/) for job scheduling and automated tasks.
- [**pytz**](https://pythonhosted.org/pytz/) for timezone handling in scheduled operations.

### Data Processing & Utilities
- [**python-dotenv**](https://python-dotenv.readthedocs.io/) for environment variable management.

## Relevant Models

  - [**Claude 3 
  Haiku**](https://docs.aws.amazon.com/bedrock/latest/userguidebedrock-runtime_example_bedrock-runtime_InvokeModel_AnthropicClaude_section.html) for text generation and content analysis through AWS Bedrock.
  - [**Cohere Embed English v3**](https://docs.aws.amazon.com/bedrocklatestuserguide/model-parameters-embed.html) for
  generating 1024-dimensional vector embeddings for
   semantic search.
  - [**Tavily Search API**](https://tavily.com/)
  for primary topic research and content discovery. 

### Key Components

#### API Endpoints (`backend/routers/`)

- **Content Router (`content.py`):**  
  Exposes endpoints for fetching content suggestions, news articles, Reddit posts, and user profiles. It acts as the main interface for clients to access aggregated and analyzed content.

- **Drafts Router (`drafts.py`):**  
  Provides CRUD operations for user-generated drafts. Supports user-specific access control, allowing secure creation, editing, and deletion of draft documents.

- **Services Router (`services.py`):**  
  Offers advanced service endpoints, such as topic research and AI-powered content analysis. Enables integration with external tools and APIs for enhanced functionality.


#### Data Processing Pipeline

- **News Scraper (`scrapers/news_scraper.py`):**  
  Continuously collects articles from multiple news sources and categories. The scraper normalizes and stores articles in the database, preparing them for downstream processing and analysis.

- **Reddit Scraper (`scrapers/social_listening.py`):**  
  Monitors and scrapes posts from configured subreddits using the PRAW library. Extracted posts are mapped to relevant topics and stored for semantic analysis and search.

- **Embedding Processor (`embeddings/process_embeddings.py`):**  
  Transforms ingested news and Reddit content into high-dimensional vector embeddings using Cohere Embed English model via AWS Bedrock. These embeddings power semantic search and similarity matching across the microservice.

- **Content Analyzer (`bedrock/llm_output.py`):**  
  Utilizes Anthropic Claude models through AWS Bedrock to analyze and summarize content. Generates structured insights (topics, keywords, descriptions, labels) in JSON format, supporting automated suggestions and research.

#### Scheduler (`scheduler/data_scheduler.py`)

Automated daily jobs ensure the microservice remains current and efficient:
- **News scraping at 15:45 UTC:** Ingests the latest news articles from configured sources.
- **Reddit scraping at 15:55 UTC:** Collects new Reddit posts and comments for analysis.
- **Embedding processing at 16:03 UTC:** Generates semantic embeddings for all newly ingested content.
- **Content suggestion generation at 16:05 UTC:** Creates AI-powered suggestions based on analyzed data.
- **Cleanup tasks:** Regularly prunes collections to maintain size limits and optimize performance.

+ This microservice architecture enables scalable, automated, and intelligent content analysis, making it ideal for integration into larger platforms or as a standalone backend for content-driven applications.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- **MongoDB Atlas** account - [Register Here](https://account.mongodb.com/account/register)
- **Python 3.10 or higher** (but less than 3.11)
- **Poetry** - [Install Here](https://python-poetry.org/docs/#installation)
- **AWS CLI** configured with appropriate credentials - [Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **AWS Account** with Bedrock access enabled - [Sign up Here](https://aws.amazon.com/bedrock/)
- **Reddit Developer Account** for API access - [Apply Here](https://www.reddit.com/prefs/apps)
- **NewsAPI Account** for news aggregation - [Get API Key](https://newsapi.org/register)
- **Tavily Search API** account - [Register Here](https://tavily.com/)
- **Docker** (optional, for containerized deployment) - [Install Here](https://docs.docker.com/get-docker/)

## Setup Instructions

### Step 1: Set Up MongoDB Database and Collections

1. Log in to MongoDB Atlas and create a database named contentlab. Ensure the name is reflected in the environment variables.

2. Create the following collections if they do not
  already exist:
  - `news` (for storing scraped news articles with
  embeddings)
  - `reddit_posts` (for storing Reddit posts and
  comments with embeddings)
  - `suggestions` (for storing AI-generated content
  suggestions)
  - `drafts` (for storing user-created draft
  documents)
  - `userProfiles` (for storing user profile
  information and preferences)

### Step 2: Add MongoDB User

Follow [MongoDB's guide](https://www.mongodb.com/docs/atlas/security-add-mongodb-users/) to create a user with **readWrite** access to the `contentlab` database.

## Configure Environment Variables

> [!IMPORTANT]
> Create a `.env` file in the `/backend` directory with the following content:
>
> ```bash
> MONGODB_URI=your_mongod_uri
>DATABASE_NAME=dbname
>APP_NAME=appname
>NEWS_COLLECTION=news
>REDDIT_COLLECTION=reddit_posts
>SUGGESTION_COLLECTION=suggestions
>USER_PROFILES_COLLECTION=userProfiles
>DRAFTS_COLLECTION=drafts
>AWS_REGION=us-east-1
>NEWSAPI_KEY=your_newsapi_key
>TAVILY_API_KEYS=your_tavily_key1,your_tavily_key2
>REDDIT_CLIENT_ID=your_reddit_client_id
>REDDIT_SECRET=your_reddit_secret
>REDDIT_USER_AGENT=your_reddit_user_agent
> ```

## Running the Backend

### Virtual Environment Setup with Poetry

1. Open a terminal in the project root directory.
2. Run the following commands:
   ```bash
   make poetry_start
   make poetry_install
   ```
3. Verify that the `.venv` folder has been generated within the `/backend` directory.

### Start the Backend

To start the backend service, run:

```bash
poetry run uvicorn main:app --host 0.0.0.0 --port 8000
```

> Default port is `8000`, modify the `--port` flag if needed.

## Running with Docker

Run the following command in the root directory:

```bash
make build
```

To remove the container and image:

```bash
make clean
```

## API Documentation

You can access the API documentation by visiting the following URL:

```
http://localhost:<PORT_NUMBER>/docs
```
E.g. `http://localhost:8000/docs`

> [!NOTE]
> Make sure to replace `<PORT_NUMBER>` with the port number you are using and ensure the backend is running.

## Common errors

> [!IMPORTANT]
> Check that you've created an `.env` file that contains the required environment variables.
