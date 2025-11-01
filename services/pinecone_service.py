# # services/pinecone_service.py

# from typing import List, Dict, Any
# from sentence_transformers import SentenceTransformer
# from pinecone import Pinecone,ServerlessSpec
# import os

# class PineconeService:
#     def __init__(self, index_name: str = "rcm-validation", dimension: int = 768, metric: str = "cosine", region: str = "us-west1"): 
#         api_key = os.getenv("PINECONE_API_KEY")
#         if not api_key:
#             raise ValueError("Missing Pinecone API Key in environment variables")

#         # Create Pinecone client instance
#         self.pc = Pinecone(api_key=api_key)

#         self.index_name = index_name
#         # Check if index exists, else create
#         if not self.pc.has_index(self.index_name):
#             # You might choose to specify spec, region, metric here
#             spec = ServerlessSpec(cloud="aws", region=region)
#             self.pc.create_index(
#                 name=self.index_name,
#                 dimension=dimension,
#                 metric=metric,
#                 spec=spec
#             )

#         self.index = self.pc.Index(self.index_name)
#         # Load local HF model (no HF key needed for public models)
#         self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

#     async def upsert_claims(self, claims: List[Dict[str, Any]]):
#         vectors = []
#         for claim in claims:
#             text = f"{claim.get('unique_id', '')} {claim.get('service_code', '')} {' '.join(claim.get('diagnosis_codes', []))}"
#             embedding = self.embedder.encode(text).tolist()
#             vectors.append((claim["unique_id"], embedding, {"tenant_id": claim.get("tenant_id", "default")}))

#             # text = f"{claim.get('unique_id', '')} {claim.get('service_code', '')} {' '.join(claim.get('diagnosis_codes', []))}"
#             # embedding = self.embedder.encode(text).tolist()
#             # vectors.append((claim["unique_id"], embedding, {"tenant_id": claim.get("tenant_id", "default")}))

#         # Upsert into index
#         self.index.upsert(vectors=vectors)

#     async def search_similar_claims(self, query: str, top_k: int = 5, filter_metadata: Dict[str, Any] = None):
#         emb = self.embedder.encode(query).tolist()
#         query_params: Dict[str, Any] = {"vector": emb, "top_k": top_k, "include_metadata": True}
#         if filter_metadata:
#             query_params["filter"] = filter_metadata

#         res = self.index.query(**query_params)
#         return res.matches

#     def delete_claims(self, unique_ids: List[str]):
#         self.index.delete(ids=unique_ids)


# services/pinecone_service.py - REPLACE ENTIRE FILE

from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
import os

class PineconeService:
    def __init__(self, index_name: str = "rcm-validation", dimension: int = 768, metric: str = "cosine", region: str = "us-west1"): 
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("Missing Pinecone API Key in environment variables")

        try:
            # Create Pinecone client instance
            self.pc = Pinecone(api_key=api_key)
            self.index_name = index_name
            
            # Check if index exists, else create
            if not self.pc.has_index(self.index_name):
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
            print(f"✅ Pinecone service initialized with index: {self.index_name}")
            
        except Exception as e:
            print(f"❌ Failed to initialize Pinecone service: {e}")
            raise

    async def upsert_claims(self, claims: List[Dict[str, Any]]):
        """Upsert claims into Pinecone with error handling"""
        try:
            vectors = []
            for claim in claims:
                try:
                    # Create text representation of claim
                    text = f"{claim.get('unique_id', '')} {claim.get('service_code', '')} {' '.join(claim.get('diagnosis_codes', []))}"
                    
                    # Generate embedding
                    embedding = self.embedder.encode(text).tolist()
                    
                    # Prepare vector with metadata
                    vectors.append((
                        claim["unique_id"], 
                        embedding, 
                        {"tenant_id": claim.get("tenant_id", "default")}
                    ))
                except Exception as e:
                    print(f"⚠️ Failed to process claim {claim.get('unique_id', 'unknown')}: {e}")
                    continue

            # Upsert into index in batches
            if vectors:
                batch_size = 100
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i:i + batch_size]
                    try:
                        self.index.upsert(vectors=batch)
                    except Exception as e:
                        print(f"⚠️ Failed to upsert batch {i//batch_size + 1}: {e}")
                
                print(f"✅ Successfully upserted {len(vectors)} claims to Pinecone")
            else:
                print("⚠️ No valid vectors to upsert")
                
        except Exception as e:
            print(f"❌ Error in upsert_claims: {e}")
            raise

    async def search_similar_claims(self, query: str, top_k: int = 5, filter_metadata: Dict[str, Any] = None):
        """Search for similar claims with error handling"""
        try:
            # Generate query embedding
            emb = self.embedder.encode(query).tolist()
            
            # Prepare query parameters
            query_params: Dict[str, Any] = {
                "vector": emb, 
                "top_k": top_k, 
                "include_metadata": True
            }
            
            if filter_metadata:
                query_params["filter"] = filter_metadata

            # Execute query
            res = self.index.query(**query_params)
            return res.matches
            
        except Exception as e:
            print(f"❌ Error in search_similar_claims: {e}")
            return []

    def delete_claims(self, unique_ids: List[str]):
        """Delete claims by IDs with error handling"""
        try:
            if not unique_ids:
                print("⚠️ No IDs provided for deletion")
                return
            
            # Delete in batches
            batch_size = 100
            for i in range(0, len(unique_ids), batch_size):
                batch = unique_ids[i:i + batch_size]
                try:
                    self.index.delete(ids=batch)
                except Exception as e:
                    print(f"⚠️ Failed to delete batch {i//batch_size + 1}: {e}")
            
            print(f"✅ Successfully deleted {len(unique_ids)} claims from Pinecone")
            
        except Exception as e:
            print(f"❌ Error in delete_claims: {e}")
            raise
    
    def get_index_stats(self):
        """Get index statistics for monitoring"""
        try:
            stats = self.index.describe_index_stats()
            return stats
        except Exception as e:
            print(f"❌ Error getting index stats: {e}")
            return None