from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import upload

# Create all tables in SQLite on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CV Sorter API",
    description="AI-powered CV analysis and ranking system",
    version="1.0.0"
)

# CORS — allows your React frontend (localhost:5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)

@app.get("/")
def root():
    return {"status": "CV Sorter API is running"}