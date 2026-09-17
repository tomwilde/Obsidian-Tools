from fastapi import FastAPI

app = FastAPI(title="Obsidian MCP Server")

@app.get("/")
async def root():
    return {"message": "Welcome to the Obsidian MCP Server"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
