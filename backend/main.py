# ---- main.py ----

# This file is used to run the FastAPI application.

# Import the necessary libraries.

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import threading
from dotenv import load_dotenv
# Import the routers.
from routers.drafts import router as drafts_router
from routers.content import router as content_router
from routers.services import router as services_router
from routers.scheduler import router as scheduler_router
from scheduler_job.data_scheduler import schedule

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Defining the FastAPI app
app = FastAPI(
    title="Content Lab Search API", 
    version="0.0.1",
    redirect_slashes=False
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers to the client
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Include the routers.
app.include_router(drafts_router)
app.include_router(content_router)
app.include_router(services_router)
app.include_router(scheduler_router)

# Run the scheduler in a separate thread
def run_scheduler():
    """Run the scheduler in a separate thread"""
    import os
    from scheduler_job.data_scheduler import schedule_jobs
    
    # Get NODE_ENV to determine if scheduler should run
    node_env = os.getenv("NODE_ENV", "").lower()
    
    logger.info("Starting scheduler thread")
    
    # Schedule jobs based on environment
    schedule_jobs()
    
    # Display scheduler overview on startup (only in prod)
    if node_env == "prod":
        logger.info("Scheduler Overview:")
        logger.info(str(schedule))
    else:
        logger.info(f"Scheduler started but no jobs scheduled (NODE_ENV={node_env}). API endpoints remain available for manual job execution.")
    
    import time
    while True:
        schedule.exec_jobs()
        time.sleep(1)


scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Test endpoint
@app.get("/")
async def read_root(request: Request):
    return {"message":"Server is running"}
