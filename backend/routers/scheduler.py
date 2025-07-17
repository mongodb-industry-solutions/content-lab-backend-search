from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging
from datetime import datetime
import pytz
import sys
import os

# Add the parent directory to the path to import scheduler_job
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler_job.data_scheduler import (
    schedule,
    run_news_scraper,
    run_reddit_scraper,
    process_embeddings,
    generate_content_suggestions,
    log_scheduler_status,
    test_scheduler_job
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

class SchedulerStatus(BaseModel):
    status: str
    current_time: str
    jobs_count: int
    message: str

class JobResult(BaseModel):
    job_name: str
    status: str
    message: str
    timestamp: str

@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status():
    """Get current scheduler status"""
    try:
        now = datetime.now(pytz.UTC)
        jobs_count = len(schedule.jobs)
        
        return SchedulerStatus(
            status="running",
            current_time=now.isoformat(),
            jobs_count=jobs_count,
            message=f"Scheduler is running with {jobs_count} scheduled jobs"
        )
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs")
async def get_scheduled_jobs():
    """Get list of all scheduled jobs"""
    try:
        jobs_info = []
        for job in schedule.jobs:
            job_info = {
                "job_id": id(job),
                "job_func": getattr(job, 'job_func', {}).get('__name__', 'unknown') if hasattr(job, 'job_func') else "unknown",
                "interval": str(getattr(job, 'interval', 'unknown')),
                "start_day": getattr(job, 'start_day', None)
            }
            
            # Try to get next run time safely
            if hasattr(job, 'next_run') and job.next_run:
                job_info["next_run"] = job.next_run.isoformat()
            elif hasattr(job, 'next_run_time') and job.next_run_time:
                job_info["next_run"] = job.next_run_time.isoformat()
            else:
                job_info["next_run"] = None
                
            jobs_info.append(job_info)
        return {"jobs": jobs_info}
    except Exception as e:
        logger.error(f"Error getting scheduled jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/news-scraper/run", response_model=JobResult)
async def run_news_scraper_manually():
    """Manually trigger news scraper job"""
    try:
        now = datetime.now(pytz.UTC)
        run_news_scraper()
        return JobResult(
            job_name="news_scraper",
            status="completed",
            message="News scraper job executed successfully",
            timestamp=now.isoformat()
        )
    except Exception as e:
        logger.error(f"Error running news scraper: {e}")
        return JobResult(
            job_name="news_scraper",
            status="failed",
            message=str(e),
            timestamp=datetime.now(pytz.UTC).isoformat()
        )

@router.post("/jobs/reddit-scraper/run", response_model=JobResult)
async def run_reddit_scraper_manually():
    """Manually trigger Reddit scraper job"""
    try:
        now = datetime.now(pytz.UTC)
        run_reddit_scraper()
        return JobResult(
            job_name="reddit_scraper",
            status="completed",
            message="Reddit scraper job executed successfully",
            timestamp=now.isoformat()
        )
    except Exception as e:
        logger.error(f"Error running Reddit scraper: {e}")
        return JobResult(
            job_name="reddit_scraper",
            status="failed",
            message=str(e),
            timestamp=datetime.now(pytz.UTC).isoformat()
        )

@router.post("/jobs/embeddings/run", response_model=JobResult)
async def run_embeddings_manually():
    """Manually trigger embeddings processing job"""
    try:
        now = datetime.now(pytz.UTC)
        process_embeddings()
        return JobResult(
            job_name="embeddings_processor",
            status="completed",
            message="Embeddings processing job executed successfully",
            timestamp=now.isoformat()
        )
    except Exception as e:
        logger.error(f"Error running embeddings processor: {e}")
        return JobResult(
            job_name="embeddings_processor",
            status="failed",
            message=str(e),
            timestamp=datetime.now(pytz.UTC).isoformat()
        )

@router.post("/jobs/content-suggestions/run", response_model=JobResult)
async def run_content_suggestions_manually():
    """Manually trigger content suggestions generation job"""
    try:
        now = datetime.now(pytz.UTC)
        generate_content_suggestions()
        return JobResult(
            job_name="content_suggestions",
            status="completed",
            message="Content suggestions generation job executed successfully",
            timestamp=now.isoformat()
        )
    except Exception as e:
        logger.error(f"Error running content suggestions generator: {e}")
        return JobResult(
            job_name="content_suggestions",
            status="failed",
            message=str(e),
            timestamp=datetime.now(pytz.UTC).isoformat()
        )

@router.post("/jobs/test/run", response_model=JobResult)
async def run_test_job_manually():
    """Manually trigger test scheduler job"""
    try:
        now = datetime.now(pytz.UTC)
        test_scheduler_job()
        return JobResult(
            job_name="test_scheduler",
            status="completed",
            message="Test scheduler job executed successfully",
            timestamp=now.isoformat()
        )
    except Exception as e:
        logger.error(f"Error running test scheduler job: {e}")
        return JobResult(
            job_name="test_scheduler",
            status="failed",
            message=str(e),
            timestamp=datetime.now(pytz.UTC).isoformat()
        )

@router.get("/logs")
async def get_scheduler_logs():
    """Get scheduler status information"""
    try:
        log_scheduler_status()
        now = datetime.now(pytz.UTC)
        return {
            "message": "Scheduler status logged successfully",
            "timestamp": now.isoformat(),
            "scheduled_jobs": {
                "news_scraper": "Daily at 04:00 UTC",
                "reddit_scraper": "Daily at 04:15 UTC", 
                "embeddings_processor": "Daily at 04:30 UTC",
                "content_suggestions": "Daily at 04:45 UTC",
                "status_checks": "Every 4 hours",
                "test_job": "Every minute"
            }
        }
    except Exception as e:
        logger.error(f"Error getting scheduler logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scheduler-overview")
async def scheduler_overview():
    """Get structured scheduler overview with clean JSON response"""
    try:
        overview = str(schedule)
        overview_lines = overview.split("\n")
        
        # Parse the header line (first line)
        header_parts = overview_lines[0].split(",")
        overview_dict = {
            "max_exec": header_parts[0].split("=")[1].strip() if len(header_parts) > 0 else "unknown",
            "tzinfo": header_parts[1].split("=")[1].strip() if len(header_parts) > 1 else "unknown", 
            "priority_function": header_parts[2].split("=")[1].strip() if len(header_parts) > 2 else "unknown",
            "jobs": []
        }
        
        # Parse job lines (skip header and separator lines)
        for line in overview_lines[3:]:
            if line.strip() and not line.startswith("--------"):
                parts = line.split()
                if len(parts) >= 6:
                    job = {
                        "type": parts[0],
                        "function": parts[1],
                        "due_at": f"{parts[2]} {parts[3]}" if len(parts) > 3 else parts[2],
                        "due_in": parts[4] if len(parts) > 4 else "",
                        "attempts": parts[5] if len(parts) > 5 else "",
                        "weight": parts[6] if len(parts) > 6 else ""
                    }
                    
                    # Clean up function names for better readability
                    if job["function"] == "#heduler_job(..)":
                        job["function"] = "test_scheduler_job"
                    elif job["function"] == "#uler_status(..)":
                        job["function"] = "log_scheduler_status"
                    elif job["function"] == "#ews_scraper(..)":
                        job["function"] = "run_news_scraper"
                    elif job["function"] == "#dit_scraper(..)":
                        job["function"] = "run_reddit_scraper"
                    elif job["function"] == "#_embeddings(..)":
                        job["function"] = "process_embeddings"
                    elif job["function"] == "#suggestions(..)":
                        job["function"] = "generate_content_suggestions"
                    
                    # Add "d" to single digit due_in values
                    if job["due_in"].isdigit():
                        job["due_in"] += "d"
                    
                    overview_dict["jobs"].append(job)
                    
        return {
            "overview": overview_dict,
            "timestamp": datetime.now(pytz.UTC).isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating structured scheduler overview: {e}")
        return {
            "error": "Failed to generate scheduler overview",
            "timestamp": datetime.now(pytz.UTC).isoformat()
        }