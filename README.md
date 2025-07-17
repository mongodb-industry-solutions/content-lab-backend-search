# **ContentLab - Automated Content Analysis & Suggestion Engine**

This repository hosts the backend for the ContentLab - Automated Content Analysis & Suggestion Engine service. The service uses FastAPI to deliver smart content insights, including semantic search, automated content aggregation, and AI-generated insights. It uses MongoDB for scalable storage and vector search, with scheduled jobs for continuous data ingestion and analysis. Designed for content creators and analysts, it transforms raw news and social media data into actionable, searchable intelligence.

## High Level Architecture

[High level architecture diagram here use [google slides](https://docs.google.com/presentation/d/1vo8Y8mBrocJtzvZc_tkVHZTsVW_jGueyUl-BExmVUtI/edit#slide=id.g30c066974c7_0_3536)]


## Key Features

**1. 




## Tech Stack

[List your tech stackexample below]

- [MongoDB Atlas](https://www.mongodb.com/atlas/database) for the database

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.10 or higher (but less than 3.11)
- Poetry (install via [Poetry's official documentation](https://python-poetry.org/docs/#installation))

[Add more if needed]

## Run it Locally

### Backend

1. (Optional) Set your project description and author information in the `pyproject.toml` file:
   ```toml
   description = "Your Description"
   authors = ["Your Name <you@example.com>"]
2. Open the project in your preferred IDE (the standard for the team is Visual Studio Code).
3. Open the Terminal within Visual Studio Code.
4. Ensure you are in the root project directory where the `makefile` is located.
5. Execute the following commands:
  - Poetry start
    ````bash
    make poetry_start
    ````
  - Poetry install
    ````bash
    make poetry_install
    ````
6. Verify that the `.venv` folder has been generated within the `/backend` directory.

## Run with Docker

Make sure to run this on the root directory.

1. To run with Docker use the following command:
```
make build
```
2. To delete the container and image run:
```
make clean
```

## Common errors

### Backend

- Check that you've created an `.env` file that contains your valid (and working) API keys, environment and index variables.