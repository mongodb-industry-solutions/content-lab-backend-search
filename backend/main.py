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

# Create the FastAPI application.
app = FastAPI()

# Add the CORS middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routers.
app.include_router(drafts_router)
app.include_router(content_router)
app.include_router(services_router)
app.include_router(scheduler_router)

# Run the scheduler in a separate thread
def run_scheduler():
    """Run the scheduler in a separate thread"""
    logger.info("Starting scheduler thread")
    
    # Display scheduler overview on startup
    logger.info("Scheduler Overview:")
    logger.info(str(schedule))
    
    import time
    while True:
        
        schedule.exec_jobs()
        time.sleep(1)


scheduler_thread = threading.Thread(target=run_scheduler)
scheduler_thread.start()

# Test endpoint
@app.get("/")
async def read_root(request: Request):
    return {"message":"Server is running"}

# Run the FastAPI application - main entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)