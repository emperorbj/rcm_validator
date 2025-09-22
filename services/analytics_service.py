# from database.mongodb import MongoDB
# from typing import Dict, List, Any
# from datetime import datetime

# class AnalyticsService:
#     def __init__(self, db: MongoDB):
#         self.db = db

#     async def generate_analytics(self, tenant_id: str) -> Dict[str, Any]:
#         """Aggregate analytics after validation."""
#         error_summary = await self.db.aggregate_claims_by_error_type(tenant_id)
#         validation_summary = await self.db.get_validation_summary(tenant_id)

#         total_claims = validation_summary.get("total", 0)
#         charts = []
#         amounts = []
#         for item in error_summary:
#             percentage = (item["claim_count"] / total_claims * 100) if total_claims else 0
#             charts.append({
#                 "category": item["error_category"],
#                 "value": item["claim_count"],
#                 "count": item["claim_count"],
#                 "percentage": percentage
#             })
#             amounts.append({
#                 "category": item["error_category"],
#                 "value": item["total_paid_amount"],
#                 "count": item["claim_count"]
#             })

#         analytics = {
#             "tenant_id": tenant_id,
#             "total_claims": total_claims,
#             "validation_summary": validation_summary,
#             "error_distribution": error_summary,
#             "claims_by_error_chart": charts,
#             "amounts_by_error_chart": amounts,
#             "generated_at": datetime.utcnow()
#         }
#         await self.db.upsert_analytics(error_summary)
#         return analytics

#     async def get_analytics_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
#         return await self.db.get_analytics_by_tenant(tenant_id)

#     async def get_comprehensive_analytics(self, tenant_id: str) -> Dict[str, Any]:
#         """Return the latest comprehensive analytics for a tenant."""
#         return await self.generate_analytics(tenant_id)
# services/analytics_service.py - Fixed version


from database.mongodb import MongoDB
from typing import Dict, List, Any
from datetime import datetime

class AnalyticsService:
    def __init__(self, db: MongoDB):
        self.db = db
    
    async def generate_analytics(self, tenant_id: str) -> Dict[str, Any]:
        """Aggregate analytics after validation."""
        error_summary = await self.db.aggregate_claims_by_error_type(tenant_id)
        validation_summary = await self.db.get_validation_summary(tenant_id)
        
        total_claims = validation_summary.get("total", 0)
        charts = []
        amounts = []
        
        # Process error summary and add tenant_id to each record
        analytics_data = []
        for item in error_summary:
            percentage = (item["claim_count"] / total_claims * 100) if total_claims else 0
            charts.append({
                "category": item["error_category"],
                "value": item["claim_count"],
                "count": item["claim_count"],
                "percentage": percentage
            })
            amounts.append({
                "category": item["error_category"],
                "value": item["total_paid_amount"],
                "count": item["claim_count"]
            })
            
            # Add tenant_id to the analytics data for storage
            analytics_data.append({
                "tenant_id": tenant_id,  # This was missing!
                "error_category": item["error_category"],
                "claim_count": item["claim_count"],
                "total_paid_amount": item["total_paid_amount"],
                "percentage": percentage,
                "generated_at": datetime.utcnow()
            })
        
        analytics = {
            "tenant_id": tenant_id,
            "total_claims": total_claims,
            "validation_summary": validation_summary,
            "error_distribution": error_summary,
            "claims_by_error_chart": charts,
            "amounts_by_error_chart": amounts,
            "generated_at": datetime.utcnow()
        }
        
        # Store analytics with tenant_id included
        if analytics_data:
            await self.db.upsert_analytics(analytics_data)
        else:
            print(f"No analytics data to store for tenant {tenant_id}")
        
        return analytics
    
    async def get_analytics_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        return await self.db.get_analytics_by_tenant(tenant_id)
    
    async def get_comprehensive_analytics(self, tenant_id: str) -> Dict[str, Any]:
        """Return the latest comprehensive analytics for a tenant."""
        return await self.generate_analytics(tenant_id)