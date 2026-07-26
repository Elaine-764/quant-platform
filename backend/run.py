import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True, 
        reload_dirs=["api", "data", "core_logic", "evaluation", "factors", "strategies", "visuals"],  # Explicitly name the folders you want to watch
    )
