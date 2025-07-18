# **Content Lab - Automated Content Analysis & Suggestion Engine**

This repository hosts the backend for the ContentLab - Automated Content Analysis & Suggestion Engine service. The service uses FastAPI to deliver smart content insights, including semantic search, automated content aggregation, and AI-generated insights. It uses MongoDB for scalable storage and vector search, with scheduled jobs for continuous data ingestion and analysis. Designed for content creators and analysts, it transforms raw news and social media data into actionable, searchable intelligence.

## High Level Architecture

[High level architecture diagram here use [google slides](https://docs.google.com/presentation/d/1vo8Y8mBrocJtzvZc_tkVHZTsVW_jGueyUl-BExmVUtI/edit#slide=id.g30c066974c7_0_3536)]


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

### Backend

- Check that you've created an `.env` file that contains your valid (and working) API keys, environment and index variables.