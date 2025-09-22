# services/pinecone_service.py

from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone,ServerlessSpec
import os

class PineconeService:
    def __init__(self, index_name: str = "rcm-validation", dimension: int = 768, metric: str = "cosine", region: str = "us-west1"): 
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("Missing Pinecone API Key in environment variables")

        # Create Pinecone client instance
        self.pc = Pinecone(api_key=api_key)

        self.index_name = index_name
        # Check if index exists, else create
        if not self.pc.has_index(self.index_name):
            # You might choose to specify spec, region, metric here
            spec = ServerlessSpec(cloud="aws", region=region)
            self.pc.create_index(
                name=self.index_name,
                dimension=dimension,
                metric=metric,
                spec=spec
            )

        self.index = self.pc.Index(self.index_name)
        # Load local HF model (no HF key needed for public models)
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    async def upsert_claims(self, claims: List[Dict[str, Any]]):
        vectors = []
        for claim in claims:
            text = f"{claim.get('claim_id', '')} {claim.get('service_code', '')} {' '.join(claim.get('diagnosis_codes', []))}"
            embedding = self.embedder.encode(text).tolist()
            vectors.append((claim["claim_id"], embedding, {"tenant_id": claim.get("tenant_id", "default")}))

        # Upsert into index
        self.index.upsert(vectors=vectors)

    async def search_similar_claims(self, query: str, top_k: int = 5, filter_metadata: Dict[str, Any] = None):
        emb = self.embedder.encode(query).tolist()
        query_params: Dict[str, Any] = {"vector": emb, "top_k": top_k, "include_metadata": True}
        if filter_metadata:
            query_params["filter"] = filter_metadata

        res = self.index.query(**query_params)
        return res.matches

    def delete_claims(self, claim_ids: List[str]):
        self.index.delete(ids=claim_ids)
