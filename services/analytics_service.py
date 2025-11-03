


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
        
#         # Process error summary and add tenant_id to each record
#         analytics_data = []
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
            
#             # Add tenant_id to the analytics data for storage
#             analytics_data.append({
#                 "tenant_id": tenant_id,  # This was missing!
#                 "error_category": item["error_category"],
#                 "claim_count": item["claim_count"],
#                 "total_paid_amount": item["total_paid_amount"],
#                 "percentage": percentage,
#                 "generated_at": datetime.utcnow()
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
        
#         # Store analytics with tenant_id included
#         if analytics_data:
#             await self.db.upsert_analytics(analytics_data)
#         else:
#             print(f"No analytics data to store for tenant {tenant_id}")
        
#         return analytics
    
#     async def get_analytics_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
#         return await self.db.get_analytics_by_tenant(tenant_id)
    
#     async def get_comprehensive_analytics(self, tenant_id: str) -> Dict[str, Any]:
#         """Return the latest comprehensive analytics for a tenant."""
#         return await self.generate_analytics(tenant_id)


# services/analytics_service.py - REPLACE entire file

from database.mongodb import MongoDB
from typing import Dict, List, Any
from datetime import datetime

class AnalyticsService:
    def __init__(self, db: MongoDB):
        self.db = db
    
    async def generate_analytics(self, tenant_id: str) -> Dict[str, Any]:
        """Generate accurate analytics with proper error categorization"""
        
        # Get all claims for tenant
        all_claims = await self.db.get_claims_by_tenant(tenant_id, skip=0, limit=10000)
        
        if not all_claims:
            return {
                "tenant_id": tenant_id,
                "total_claims": 0,
                "validation_summary": {
                    "total": 0,
                    "validated": 0,
                    "not_validated": 0
                },
                "error_summary": {
                    "technical_only": 0,
                    "medical_only": 0,
                    "both_errors": 0,
                    "no_errors": 0,
                    "total_errors": 0
                },
                "error_distribution": [],
                "claims_by_error_chart": [],
                "amounts_by_error_chart": [],
                "generated_at": datetime.utcnow()
            }
        
        # Initialize counters
        total_claims = len(all_claims)
        validated_count = 0
        not_validated_count = 0
        
        # Error type counters
        technical_only = 0
        medical_only = 0
        both_errors = 0
        no_errors = 0
        
        # Error category totals
        error_categories = {
            "No error": {"count": 0, "amount": 0.0},
            "Technical error": {"count": 0, "amount": 0.0},
            "Medical error": {"count": 0, "amount": 0.0},
            "Both": {"count": 0, "amount": 0.0}
        }
        
        # Process each claim
        for claim in all_claims:
            status = claim.get("status", "Pending")
            error_type = claim.get("error_type", "No error")
            paid_amount = float(claim.get("paid_amount_aed", 0))
            
            # Count validation status
            if status == "Validated":
                validated_count += 1
            else:
                not_validated_count += 1
            
            # Count error types
            if error_type == "No error":
                no_errors += 1
            elif error_type == "Technical error":
                technical_only += 1
            elif error_type == "Medical error":
                medical_only += 1
            elif error_type == "Both":
                both_errors += 1
            
            # Aggregate by error category
            if error_type in error_categories:
                error_categories[error_type]["count"] += 1
                error_categories[error_type]["amount"] += paid_amount
        
        # Calculate total errors
        total_errors = technical_only + medical_only + both_errors
        
        # Create validation summary
        validation_summary = {
            "total": total_claims,
            "validated": validated_count,
            "not_validated": not_validated_count
        }
        
        # Create error summary
        error_summary = {
            "technical_only": technical_only,
            "medical_only": medical_only,
            "both_errors": both_errors,
            "no_errors": no_errors,
            "total_errors": total_errors
        }
        
        # Create error distribution for charts
        error_distribution = []
        claims_by_error_chart = []
        amounts_by_error_chart = []
        
        for category, data in error_categories.items():
            if data["count"] > 0:  # Only include categories with claims
                percentage = (data["count"] / total_claims * 100) if total_claims > 0 else 0
                
                error_distribution.append({
                    "error_category": category,
                    "claim_count": data["count"],
                    "total_paid_amount": data["amount"]
                })
                
                claims_by_error_chart.append({
                    "category": category,
                    "value": data["count"],
                    "count": data["count"],
                    "percentage": percentage
                })
                
                amounts_by_error_chart.append({
                    "category": category,
                    "value": data["amount"],
                    "count": data["count"]
                })
        
        analytics = {
            "tenant_id": tenant_id,
            "total_claims": total_claims,
            "validation_summary": validation_summary,
            "error_summary": error_summary,
            "error_distribution": error_distribution,
            "claims_by_error_chart": claims_by_error_chart,
            "amounts_by_error_chart": amounts_by_error_chart,
            "generated_at": datetime.utcnow()
        }
        
        # Store in analytics collection
        analytics_records = []
        for category, data in error_categories.items():
            if data["count"] > 0:
                analytics_records.append({
                    "tenant_id": tenant_id,
                    "error_category": category,
                    "claim_count": data["count"],
                    "total_paid_amount": data["amount"],
                    "percentage": (data["count"] / total_claims * 100) if total_claims > 0 else 0,
                    "generated_at": datetime.utcnow()
                })
        
        if analytics_records:
            await self.db.upsert_analytics(analytics_records)
        
        return analytics
    
    async def get_analytics_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        return await self.db.get_analytics_by_tenant(tenant_id)
    
    async def get_comprehensive_analytics(self, tenant_id: str) -> Dict[str, Any]:
        """Return the latest comprehensive analytics for a tenant"""
        return await self.generate_analytics(tenant_id)