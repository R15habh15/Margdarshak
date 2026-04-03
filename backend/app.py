"""
Margadarshak — FastAPI Entry Point
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api import simulation_api, map_api, metrics_api
from src.brain.model_manager import ModelManager

app = FastAPI(
    title="Margadarshak API",
    description="AI-Driven Smart Traffic Control System",
    version="1.0.0"
)

# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Routers
# -------------------------------------------------------------------

app.include_router(map_api.router, prefix="/api/map", tags=["Map"])
app.include_router(simulation_api.router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(metrics_api.router, prefix="/api/metrics", tags=["Metrics"])

model_manager = ModelManager()

# -------------------------------------------------------------------
# Root
# -------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Margadarshak Backend is running."}


# -------------------------------------------------------------------
# Health
# -------------------------------------------------------------------

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

@app.get("/config")
@app.get("/api/config")
def config():
    return {
        "name": "Margadarshak",
        "version": "1.0.0",
        "mode": "development",

        "sumo": {
            "enabled": True
        },

        "ml": {
            "enabled": True,
            "framework": "pytorch"
        },

        "simulation": {
            "engine": "SUMO",
            "realtime": False
        }
    }


# -------------------------------------------------------------------
# Training Endpoints
# -------------------------------------------------------------------

@app.get("/training/status")
@app.get("/api/training/status")
def training_status():
    return {
        "active": False,
        "episode": None
    }


@app.post("/training/stop")
@app.post("/api/training/stop")
def stop_training():
    raise HTTPException(status_code=400, detail="Training not running")


@app.get("/training/models")
@app.get("/api/training/models")
def list_models():
    return model_manager.list_models()


# -------------------------------------------------------------------
# Run Server
# -------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)