from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from dotenv import load_dotenv

from routers.drafts import router as drafts_router
from routers.content import router as content_router
from routers.services import router as services_router

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drafts_router)
app.include_router(content_router)
app.include_router(services_router)

@app.get("/")
async def read_root(request: Request):
    return {"message":"Server is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)