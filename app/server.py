# app/server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.database import query_db

app = FastAPI()

class Query(BaseModel):
    text: str

@app.post("/query/")
def ask_question(query: Query):
    """Receives a question and returns relevant document excerpts."""
    try:
        results = query_db(query.text)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "MCP Server is running. Post your queries to /query/"}
