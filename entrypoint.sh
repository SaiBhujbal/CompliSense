#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define paths inside the container
DATA_DIR="/app/data"
CHROMA_DB_PATH="/app/chroma_db"

echo "--- Starting Compli-Sense Container ---"

# Check if the Chroma vector store directory exists
if [ ! -d "$CHROMA_DB_PATH" ]; then
    echo "Vector store not found at $CHROMA_DB_PATH."
    echo "Starting initial data ingestion and vectorization..."
    # Run the ingestion script. This will download PDFs and create the vector store.
    python ingest_data.py
    echo "--- Ingestion Complete ---"
else
    echo "Vector store found at $CHROMA_DB_PATH. Skipping ingestion."
fi

echo "--- Starting Streamlit Application ---"
# Use 'exec' to replace the shell process with the Streamlit process.
# This ensures Streamlit is the main process (PID 1) and receives signals like SIGTERM correctly.
exec streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0