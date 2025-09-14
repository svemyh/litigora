#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import weaviate
from weaviate.classes.config import Configure
from weaviate.classes.data import DataObject
import PyPDF2
from typing import List, Dict
import hashlib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

class DocumentVectorizer:
    def __init__(self, weaviate_url: str, api_key: str = None):
        """Initialize the document vectorizer with Weaviate connection."""
        self.weaviate_url = weaviate_url
        self.api_key = api_key
        self.client = None
        self.collection_name = "Documents"

    def connect(self):
        """Connect to Weaviate cluster."""
        try:
            if self.api_key:
                self.client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=self.weaviate_url,
                    auth_credentials=weaviate.auth.AuthApiKey(self.api_key),
                    headers={
                        "X-OpenAI-Api-Key": os.getenv("OPENAI_APIKEY", "")
                    }
                )
            else:
                self.client = weaviate.connect_to_custom(
                    http_host=self.weaviate_url,
                    http_port=80,
                    http_secure=False,
                    grpc_host=self.weaviate_url,
                    grpc_port=50051,
                    grpc_secure=False,
                    headers={
                        "X-OpenAI-Api-Key": os.getenv("OPENAI_APIKEY", "")
                    }
                )
            print(f"Connected to Weaviate at {self.weaviate_url}")
        except Exception as e:
            print(f"Failed to connect to Weaviate: {e}")
            sys.exit(1)

    def create_schema(self):
        """Create the document schema in Weaviate."""
        try:
            if self.client.collections.exists(self.collection_name):
                print(f"Collection '{self.collection_name}' already exists")
                return

            collection = self.client.collections.create(
                name=self.collection_name,
                vectorizer_config=Configure.Vectorizer.text2vec_openai(),
                generative_config=Configure.Generative.openai()
            )
            print(f"Created collection '{self.collection_name}'")
        except Exception as e:
            print(f"Failed to create schema: {e}")

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file."""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num, page in enumerate(reader.pages):
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page.extract_text()
                return text
        except Exception as e:
            print(f"Failed to extract text from {pdf_path}: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            if end < len(text):
                last_space = chunk.rfind(' ')
                if last_space != -1:
                    chunk = chunk[:last_space]
                    end = start + last_space

            chunks.append(chunk.strip())
            start = end - overlap

            if start >= len(text):
                break

        return [chunk for chunk in chunks if chunk]

    def generate_chunk_id(self, filename: str, chunk_index: int, chunk_text: str) -> str:
        """Generate unique ID for each chunk."""
        content_hash = hashlib.md5(chunk_text.encode()).hexdigest()[:8]
        return f"{filename}_{chunk_index}_{content_hash}"

    def process_documents(self, assets_dir: str = "assets"):
        """Process all PDF documents in the assets directory."""
        assets_path = Path(assets_dir)
        if not assets_path.exists():
            print(f"Assets directory '{assets_dir}' not found")
            return

        pdf_files = list(assets_path.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in '{assets_dir}'")
            return

        print(f"Found {len(pdf_files)} PDF files to process")

        collection = self.client.collections.get(self.collection_name)
        total_chunks = 0

        for pdf_file in pdf_files:
            print(f"Processing: {pdf_file.name}")

            text = self.extract_text_from_pdf(str(pdf_file))
            if not text:
                continue

            chunks = self.chunk_text(text)
            print(f"  Generated {len(chunks)} chunks")

            batch_data = []
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                chunk_id = self.generate_chunk_id(pdf_file.stem, i, chunk)

                data_object = {
                    "filename": pdf_file.name,
                    "chunk_index": i,
                    "content": chunk,
                    "file_path": str(pdf_file),
                    "processed_at": datetime.now().isoformat(),
                    "chunk_id": chunk_id
                }
                batch_data.append(data_object)

            if batch_data:
                try:
                    collection.data.insert_many(batch_data)
                    total_chunks += len(batch_data)
                    print(f"  Uploaded {len(batch_data)} chunks")
                except Exception as e:
                    print(f"  Failed to upload chunks: {e}")

        print(f"Total chunks processed: {total_chunks}")

    def search_documents(self, query: str, limit: int = 5):
        """Search for documents using vector similarity."""
        try:
            collection = self.client.collections.get(self.collection_name)

            response = collection.query.near_text(
                query=query,
                limit=limit,
                return_metadata=weaviate.classes.query.MetadataQuery(score=True)
            )

            results = []
            for obj in response.objects:
                results.append({
                    "filename": obj.properties.get("filename"),
                    "chunk_index": obj.properties.get("chunk_index"),
                    "content": obj.properties.get("content")[:200] + "...",
                    "score": obj.metadata.score
                })

            return results
        except Exception as e:
            print(f"Search failed: {e}")
            return []

    def close(self):
        """Close Weaviate connection."""
        if self.client:
            self.client.close()

def main():
    """Main function to run the document vectorizer."""
    import argparse

    load_dotenv()

    parser = argparse.ArgumentParser(description="Vectorize documents for Weaviate")
    parser.add_argument("--url", default="ijn82ys1to6m0nm7ogs4na.c0.europe-west3.gcp.weaviate.cloud",
                       help="Weaviate cluster URL")
    parser.add_argument("--assets-dir", default="assets", help="Directory containing PDF files")
    parser.add_argument("--search", help="Search query to test the system")
    parser.add_argument("--create-schema", action="store_true", help="Create the schema only")

    args = parser.parse_args()

    api_key = os.getenv("WEAVIATE_API_KEY")
    if not api_key:
        print("Error: WEAVIATE_API_KEY environment variable not set")
        print("Please create a .env file with: WEAVIATE_API_KEY=your_api_key_here")
        sys.exit(1)

    openai_key = os.getenv("OPENAI_APIKEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("Error: OPENAI_APIKEY environment variable not set")
        print("Please add to .env file: OPENAI_APIKEY=your_openai_key_here")
        sys.exit(1)

    os.environ["OPENAI_APIKEY"] = openai_key

    vectorizer = DocumentVectorizer(args.url, api_key)
    vectorizer.connect()

    try:
        if args.create_schema:
            vectorizer.create_schema()
        elif args.search:
            results = vectorizer.search_documents(args.search)
            print(f"Search results for '{args.search}':")
            for i, result in enumerate(results, 1):
                print(f"{i}. {result['filename']} (chunk {result['chunk_index']}) - Score: {result['score']:.4f}")
                print(f"   {result['content']}\n")
        else:
            vectorizer.create_schema()
            vectorizer.process_documents(args.assets_dir)

    finally:
        vectorizer.close()

if __name__ == "__main__":
    main()