# Code Assistant MCP

This project provides a set of tools to help understand a codebase.

## `db_tools.py`

This script runs a FastAPI server that provides endpoints to inspect a database.

### Running the Server

To run the server, use the following command:

```bash
DATABASE_URL="postgresql://user:password@host:port/database" uv run db_tools.py
```

Replace `"postgresql://user:password@host:port/database"` with your actual database connection string.

### API Endpoints

#### Get All Tables

*   **Endpoint:** `/tables`
*   **Method:** `GET`
*   **Description:** Returns a list of all tables in the database.
*   **`curl` command:**
    ```bash
    curl http://127.0.0.1:8000/tables
    ```

#### Get Table Details

*   **Endpoint:** `/tables/{table_name}`
*   **Method:** `GET`
*   **Description:** Returns detailed information about a specific table, including its columns.
*   **`curl` command:**
    ```bash
    curl http://127.0.0.1:8000/tables/your_table_name
    ```
    Replace `your_table_name` with the actual name of the table.

#### Get Table Relationships

*   **Endpoint:** `/tables/{table_name}/relationships`
*   **Method:** `GET`
*   **Description:** Returns the foreign key relationships for a specific table. The `on_delete` field shows the action taken when a referenced row is deleted (e.g., `CASCADE`, `SET NULL`, `NO ACTION`).
*   **`curl` command:**
    ```bash
    curl http://127.0.0.1:8000/tables/your_table_name/relationships
    ```
    Replace `your_table_name` with the actual name of the table.
