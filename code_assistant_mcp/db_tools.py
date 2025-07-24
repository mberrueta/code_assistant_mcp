import logging
import os
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, inspect, text
from pydantic import BaseModel
from typing import List, Dict, Any

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

# --- Database Connection ---
# Replace with your actual database connection string
# For example: "postgresql://user:password@host:port/database"
# Or use an environment variable for better security
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./test.db")
logging.info(f"Attempting to connect to database with URL: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    # Test the connection
    with engine.connect() as connection:
        logging.info("Database connection successful.")
        pass
except Exception as e:
    logging.error(f"Error connecting to the database: {e}", exc_info=True)
    # You might want to handle this more gracefully,
    # perhaps by exiting the application if the DB is essential.
    engine = None

# --- Pydantic Models ---
class TableName(BaseModel):
    name: str

class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Any
    primary_key: bool

class TableInfo(BaseModel):
    name: str
    columns: List[ColumnInfo]

class RelationshipInfo(BaseModel):
    local_column: str
    remote_table: str
    remote_column: str
    on_delete: str | None = None


class TableRelationships(BaseModel):
    name: str
    relationships: List[RelationshipInfo]


# --- Helper Functions ---
def get_db_inspector():
    if not engine:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    try:
        return inspect(engine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating database inspector: {e}")


# --- API Endpoints ---

@app.get("/tables", response_model=List[TableName])
async def get_tables():
    """
    Get a list of all tables in the database.
    """
    inspector = get_db_inspector()
    try:
        table_names = inspector.get_table_names()
        return [{"name": name} for name in table_names]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tables: {e}")


@app.get("/tables/{table_name}", response_model=TableInfo)
async def get_table_details(table_name: str):
    """
    Get detailed information about a specific table, including its columns.
    """
    inspector = get_db_inspector()
    try:
        if not inspector.has_table(table_name):
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

        columns = inspector.get_columns(table_name)
        column_info = [
            ColumnInfo(
                name=col["name"],
                type=str(col["type"]),
                nullable=col["nullable"],
                default=col.get("default"),
                primary_key=col.get("primary_key", False),
            )
            for col in columns
        ]
        return TableInfo(name=table_name, columns=column_info)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching table details for '{table_name}': {e}")


@app.get("/tables/{table_name}/relationships", response_model=TableRelationships)
async def get_table_relationships(table_name: str):
    """
    Get the foreign key relationships for a specific table.
    """
    inspector = get_db_inspector()
    try:
        if not inspector.has_table(table_name):
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

        foreign_keys = inspector.get_foreign_keys(table_name)
        relationships = []
        for fk in foreign_keys:
            on_delete = fk.get("options", {}).get("ondelete")
            relationships.append(
                RelationshipInfo(
                    local_column=fk["constrained_columns"][0],
                    remote_table=fk["referred_table"],
                    remote_column=fk["referred_columns"][0],
                    on_delete=on_delete,
                )
            )
        return TableRelationships(name=table_name, relationships=relationships)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching relationships for '{table_name}': {e}")


if __name__ == "__main__":
    import uvicorn
    # This will run the app on http://127.0.0.1:8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
