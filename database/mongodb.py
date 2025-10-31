# database/mongodb.py
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
from bson import ObjectId

class MongoDB:
    def __init__(self):
        # MongoDB connection string - use environment variable
        self.connection_string = os.getenv(
            "MONGO_URI", 
        )
        self.client = None
        self.database = None
        self.claims = None
        
    async def connect(self):
        """Initialize MongoDB connection"""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.database = self.client.rcm_engine
            self.claims = self.database["claims_master"]
            
            # Create indexes for better performance
            await self._create_indexes()
            print("✅ Connected to MongoDB successfully")
            
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            raise
    
    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
    
    async def ping(self):
        """Test database connection"""
        if self.client:
            await self.client.admin.command('ping')
            return True
        return False
    
    async def _create_indexes(self):
        """Create database indexes for optimal performance"""
        # Claims master collection indexes
        await self.database.claims_master.create_index([
            ("tenant_id", 1), ("unique_id", 1)
        ], unique=True)
        await self.database.claims_master.create_index([
            ("tenant_id", 1), ("status", 1)
        ])
        await self.database.claims_master.create_index([
            ("tenant_id", 1), ("error_type", 1)
        ])
        
        # Rules config collection indexes
        await self.database.rules_config.create_index([
            ("tenant_id", 1)
        ], unique=True)
        
        # Analytics collection indexes
        await self.database.analytics.create_index([
            ("tenant_id", 1), ("error_category", 1)
        ])
    
    # Claims Master Collection Operations
    async def insert_many_claims(self, claims: List[Dict[str, Any]]):
        """Insert multiple claims into master table"""
        try:
            result = await self.database.claims_master.insert_many(claims)
            return result
        except DuplicateKeyError as e:
            # Handle duplicate unique_id for same tenant
            raise ValueError(f"Duplicate claim IDs found: {e}")
    
    async def get_claims_by_tenant(
        self, 
        tenant_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get paginated claims for a tenant"""
        cursor = self.database.claims_master.find(
            {"tenant_id": tenant_id}
        ).skip(skip).limit(limit).sort("uploaded_at", -1)
        
        claims = []
        async for claim in cursor:
            claim["_id"] = str(claim["_id"])  # Convert ObjectId to string
            claims.append(claim)
        
        return claims
    
    async def count_claims_by_tenant(self, tenant_id: str) -> int:
        """Count total claims for a tenant"""
        return await self.database.claims_master.count_documents(
            {"tenant_id": tenant_id}
        )
    
    async def get_pending_claims(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all pending claims for validation"""
        cursor = self.database.claims_master.find({
            "tenant_id": tenant_id,
            "status": "Pending"
        })
        
        claims = []
        async for claim in cursor:
            claim["_id"] = str(claim["_id"])
            claims.append(claim)
        
        return claims
    
    async def update_claim_validation(
        self, 
        unique_id: str, 
        tenant_id: str, 
        validation_result: Dict[str, Any]
    ):
        """Update claim with validation results"""
        result = await self.database.claims_master.update_one(
            {"unique_id": unique_id, "tenant_id": tenant_id},
            {
                "$set": {
                    "status": validation_result["status"],
                    "error_type": validation_result["error_type"],
                    "error_explanation": validation_result["error_explanation"],
                    "recommended_action": validation_result["recommended_action"],
                    "validated_at": datetime.utcnow()
                }
            }
        )
        return result
    
    async def bulk_update_claims(self, updates: List[Dict[str, Any]]):
        """Bulk update multiple claims"""
        operations = []
        for update in updates:
            operations.append({
                "filter": {
                    "unique_id": update["unique_id"],
                    "tenant_id": update["tenant_id"]
                },
                "update": {
                    "$set": {
                        "status": update["status"],
                        "error_type": update["error_type"],
                        "error_explanation": update["error_explanation"],
                        "recommended_action": update["recommended_action"],
                        "validated_at": datetime.utcnow()
                    }
                }
            })
        
        if operations:
            result = await self.database.claims_master.bulk_write([
                {"updateOne": op} for op in operations
            ])
            return result
    
    # Rules Configuration Operations
    async def upsert_rules_config(self, tenant_id: str, rules_data: Dict[str, Any]):
        """Insert or update rules configuration for a tenant"""
        result = await self.database.rules_config.update_one(
            {"tenant_id": tenant_id},
            {"$set": rules_data},
            upsert=True
        )
        return result
    
    async def get_rules_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get rules configuration for a tenant"""
        config = await self.database.rules_config.find_one(
            {"tenant_id": tenant_id}
        )
        if config:
            config["_id"] = str(config["_id"])
        return config
    
    # Analytics Operations
    
    
    # Fixed upsert_analytics method in database/mongodb.py

    async def upsert_analytics(self, analytics_data: List[Dict[str, Any]]):
        """Insert or update analytics data"""
        if not analytics_data:
            return None
            
        operations = []
        for data in analytics_data:
            # Ensure tenant_id exists in the data
            if "tenant_id" not in data:
                print(f"Warning: tenant_id missing from analytics data: {data}")
                continue
                
            # Ensure error_category exists
            if "error_category" not in data:
                print(f"Warning: error_category missing from analytics data: {data}")
                continue
                
            operations.append({
                "filter": {
                    "tenant_id": data["tenant_id"],
                    "error_category": data["error_category"]
                },
                "update": {"$set": data},
                "upsert": True
            })
        
        if operations:
            try:
                from pymongo import UpdateOne
                bulk_operations = [UpdateOne(op["filter"], op["update"], upsert=op["upsert"]) for op in operations]
                result = await self.database.analytics.bulk_write(bulk_operations)
                print(f"Analytics upsert completed: {result.upserted_count} inserted, {result.modified_count} modified")
                return result
            except Exception as e:
                print(f"Error in analytics upsert: {str(e)}")
                raise
        else:
            print("No valid analytics operations to perform")
            return None
    # async def upsert_analytics(self, analytics_data: List[Dict[str, Any]]):
    #     """Insert or update analytics data"""
    #     operations = []
    #     for data in analytics_data:
    #         operations.append({
    #             "filter": {
    #                 "tenant_id": data["tenant_id"],
    #                 "error_category": data["error_category"]
    #             },
    #             "update": {"$set": data},
    #             "upsert": True
    #         })
        
    #     if operations:
    #         result = await self.database.analytics.bulk_write([
    #             {"updateOne": op} for op in operations
    #         ])
    #         return result
    
    async def get_analytics_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get analytics data for a tenant"""
        cursor = self.database.analytics.find({"tenant_id": tenant_id})
        
        analytics = []
        async for record in cursor:
            record["_id"] = str(record["_id"])
            analytics.append(record)
        
        return analytics
    
    # Data Management Operations
    async def clear_tenant_data(self, tenant_id: str):
        """Clear all data for a tenant (for testing/reset)"""
        # Delete claims
        await self.database.claims_master.delete_many({"tenant_id": tenant_id})
        
        # Delete analytics
        await self.database.analytics.delete_many({"tenant_id": tenant_id})
        
        # Optionally keep rules config for reuse
        # await self.database.rules_config.delete_one({"tenant_id": tenant_id})
    
    # Aggregation Operations for Analytics
    async def aggregate_claims_by_error_type(self, tenant_id: str):
        """Aggregate claims count by error type"""
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {
                "$group": {
                    "_id": "$error_type",
                    "count": {"$sum": 1},
                    "total_paid_amount": {"$sum": "$paid_amount_aed"}
                }
            },
            {"$sort": {"count": -1}}
        ]
        
        cursor = self.database.claims_master.aggregate(pipeline)
        results = []
        async for doc in cursor:
            results.append({
                "error_category": doc["_id"],
                "claim_count": doc["count"],
                "total_paid_amount": doc["total_paid_amount"]
            })
        
        return results
    
    async def get_validation_summary(self, tenant_id: str):
        """Get validation summary statistics"""
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        cursor = self.database.claims_master.aggregate(pipeline)
        summary = {"total": 0, "validated": 0, "not_validated": 0}
        
        async for doc in cursor:
            summary["total"] += doc["count"]
            if doc["_id"] == "Validated":
                summary["validated"] = doc["count"]
            else:
                summary["not_validated"] = doc["count"]
        
        return summary