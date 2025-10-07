import os
import requests
import yaml
import shutil
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()

DATA_DIR = Path(os.getenv("RBI_DATA_PATH", "./data"))
CHROMA_DB_PATH = Path(os.getenv("CHROMA_DB_PATH", "./chroma_db"))
DATA_SOURCES_FILE = Path("data_sources.yaml")

def clean_data_directory():
    """Removes all existing files in the data directory."""
    if DATA_DIR.exists():
        print(f"Cleaning existing files in {DATA_DIR}...")
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("Data directory cleaned.")

def download_documents():
    """Downloads all PDFs listed in the data_sources.yaml file."""
    print("Starting document download...")
    try:
        with open(DATA_SOURCES_FILE, 'r') as f:
            sources = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {DATA_SOURCES_FILE} not found. Please create it.")
        return
    except yaml.YAMLError as e:
        print(f"Error parsing {DATA_SOURCES_FILE}: {e}")
        return

    if not sources or 'documents' not in sources:
        print("No documents found in data_sources.yaml.")
        return

    for doc in sources['documents']:
        try:
            print(f"Downloading {doc['name']} from {doc['url']}...")
            response = requests.get(doc['url'], stream=True, timeout=60)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            file_path = DATA_DIR / doc['file_name']
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Successfully downloaded {doc['file_name']}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {doc['name']}: {e}")
        except KeyError as e:
            print(f"Skipping invalid entry in YAML file. Missing key: {e}")

def create_vector_store():
    """Processes downloaded PDFs and creates/updates the Chroma vector store."""
    print("Starting vector store creation...")
    all_docs = []
    pdf_files = list(DATA_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {DATA_DIR}. Vector store will be empty.")
        return

    for pdf_file in pdf_files:
        try:
            print(f"Processing {pdf_file.name}...")
            loader = PyPDFLoader(pdf_file)
            docs = loader.load()
            all_docs.extend(docs)
        except Exception as e:
            print(f"Error loading or processing {pdf_file.name}: {e}")

    if not all_docs:
        print("No content could be extracted from the PDFs. Vector store will be empty.")
        return

    print(f"Total documents loaded: {len(all_docs)}")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    documents = text_splitter.split_documents(all_docs)
    
    print("Creating embeddings and building vector store... This may take a while.")
    # Use HuggingFace embeddings (free, no API key required)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    # If the vector store already exists, Chroma will add to it. To ensure a clean build,
    # we remove the old directory first.
    if CHROMA_DB_PATH.exists():
        shutil.rmtree(CHROMA_DB_PATH)
        
    vector_store = Chroma.from_documents(documents, embeddings, persist_directory=str(CHROMA_DB_PATH))
    print(f"Vector store successfully created and persisted at {CHROMA_DB_PATH}")

if __name__ == "__main__":
    clean_data_directory()
    download_documents()
    create_vector_store()
    print("\nData ingestion and vectorization complete.")