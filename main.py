# main.py
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form,Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
import os
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import pandas as pd
from io import BytesIO
import json
import fitz
import mimetypes

from database.mongodb import MongoDB
from models.schemas import (
    ClaimRecord, UserLogin, UserResponse, ValidationRequest,
    ValidationResponse, AnalyticsResponse, RuleUploadRequest
)
from services.rule_engine import RuleEngine
from services.validation_service import ValidationService
from services.analytics_service import AnalyticsService
from config.settings import Settings
from dotenv import load_dotenv
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="RCM Validation Engine",
    description="Healthcare Claims Validation System",
    version="1.0.0"
)




# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize settings and services
settings = Settings()
db = MongoDB()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
rule_engine = RuleEngine()
validation_service = ValidationService(db, rule_engine)
analytics_service = AnalyticsService(db)

# JWT token management
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.on_event("startup")
async def startup_event():
    """Initialize database connection and create indexes"""
    await db.connect()
    print("🚀 RCM Validation Engine started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection"""
    await db.close()
    print("👋 Application shutdown complete")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        await db.ping()
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "version": "1.0.0"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.post("/auth/login", response_model=UserResponse)
async def login(user_data: UserLogin):
    """Authenticate user and return JWT token"""
    # Simple authentication - in production, use proper user management
    if user_data.username == "admin" and user_data.password == "admin123":
        access_token = create_access_token(data={"sub": user_data.username})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user_data.username
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/upload/rules")
async def upload_rules(
    technical_rules: UploadFile = File(None),
    medical_rules: UploadFile = File(None),
    tenant_id: str = Form("default"),
    current_user: str = Depends(verify_token)
):
    """Upload technical and medical rules files (supports PDF or text)."""
    try:
        rules_data = {"tenant_id": tenant_id, "uploaded_at": datetime.utcnow()}

        async def extract_text(upload_file: UploadFile) -> str:
            """Extract text from PDF or plain text."""
            content = await upload_file.read()
            mime_type, _ = mimetypes.guess_type(upload_file.filename)
            if mime_type == "application/pdf":
                # Parse PDF
                text = ""
                with fitz.open(stream=content, filetype="pdf") as pdf:
                    for page in pdf:
                        text += page.get_text()
                return text
            else:
                # Decode plain text safely
                return content.decode("utf-8", errors="ignore")

        if technical_rules:
            rules_data["technical_rules"] = await extract_text(technical_rules)
        if medical_rules:
            rules_data["medical_rules"] = await extract_text(medical_rules)

        # Store rules configuration
        await db.upsert_rules_config(tenant_id, rules_data)

        return {
            "message": "Rules uploaded successfully",
            "tenant_id": tenant_id,
            "technical_rules_uploaded": technical_rules is not None,
            "medical_rules_uploaded": medical_rules is not None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rules upload failed: {str(e)}")
    
# main.py - REPLACE the upload_claims endpoint (around line 180)


# Replace the /upload/claims endpoint in main.py with this version

# main.py - REPLACE the upload_claims endpoint

@app.post("/upload/claims")
async def upload_claims(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    skip_duplicates: bool = Form(True),  # New parameter to control duplicate behavior
    current_user: str = Depends(verify_token)
):
    """Upload and process claims file (CSV, XLS, XLSX)"""
    try:
        # Validate file type
        filename_lower = file.filename.lower()
        if not (filename_lower.endswith('.csv') or filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls')):
            raise HTTPException(
                status_code=400, 
                detail="Only CSV, XLS, and XLSX files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Validate file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 10MB limit"
            )
        
        # Parse file based on type
        try:
            if filename_lower.endswith('.csv'):
                df = pd.read_csv(BytesIO(content))
            elif filename_lower.endswith('.xlsx'):
                df = pd.read_excel(BytesIO(content), engine='openpyxl')
            elif filename_lower.endswith('.xls'):
                df = pd.read_excel(BytesIO(content), engine='xlrd')
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error parsing file: {str(e)}"
            )
        
        # Validate required columns
        required_columns = [
            'claim_id', 'encounter_type', 'service_date', 'national_id',
            'member_id', 'facility_id', 'unique_id', 'diagnosis_codes',
            'service_code', 'paid_amount_aed', 'approval_number'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Convert to records
        claims_data = []
        skipped_rows = []
        
        for idx, row in df.iterrows():
            try:
                # Handle diagnosis codes (semicolon or comma separated)
                diagnosis_codes_str = str(row['diagnosis_codes']) if pd.notna(row['diagnosis_codes']) else ""
                if diagnosis_codes_str:
                    diagnosis_codes = [
                        code.strip() 
                        for code in diagnosis_codes_str.replace(';', ',').split(',') 
                        if code.strip()
                    ]
                else:
                    diagnosis_codes = []
                
                # Handle approval number (normalize NA values)
                approval_number = str(row['approval_number']) if pd.notna(row['approval_number']) else ""
                if approval_number.upper() in ['NA', 'N/A', 'NAN', 'NONE', 'NULL']:
                    approval_number = ""
                
                # Normalize unique_id (uppercase and add hyphens if needed)
                raw_unique_id = str(row['unique_id']).strip().upper()
                
                # If it's exactly 12 chars with no hyphens, add them
                if len(raw_unique_id.replace('-', '')) == 12:
                    clean_id = raw_unique_id.replace('-', '')
                    unique_id = f"{clean_id[0:4]}-{clean_id[4:8]}-{clean_id[8:12]}"
                else:
                    unique_id = raw_unique_id
                
                claim = {
                    "claim_id": str(row['claim_id']),
                    "unique_id": unique_id,
                    "encounter_type": str(row['encounter_type']).strip().upper(),
                    "service_date": str(row['service_date']),
                    "national_id": str(row['national_id']).strip().upper(),
                    "member_id": str(row['member_id']).strip().upper(),
                    "facility_id": str(row['facility_id']).strip().upper(),
                    "diagnosis_codes": diagnosis_codes,
                    "service_code": str(row['service_code']).strip(),
                    "paid_amount_aed": float(row['paid_amount_aed']),
                    "approval_number": approval_number,
                    "tenant_id": tenant_id,
                    "uploaded_at": datetime.utcnow(),
                    "status": "Pending",
                    "error_type": "No error",
                    "error_explanation": [],
                    "recommended_action": ""
                }
                claims_data.append(claim)
                
            except Exception as e:
                skipped_rows.append({"row": idx + 2, "error": str(e)})
                print(f"⚠️ Error processing row {idx + 2}: {str(e)}")
                continue
        
        if not claims_data:
            raise HTTPException(
                status_code=400,
                detail="No valid claims found in file"
            )
        
        # Store in database with duplicate handling
        inserted_count = 0
        duplicate_count = 0
        failed_claims = []
        
        if skip_duplicates:
            # Insert one by one to skip duplicates
            for claim in claims_data:
                try:
                    await db.database.claims_master.insert_one(claim)
                    inserted_count += 1
                except Exception as e:
                    if "E11000" in str(e):  # Duplicate key error
                        duplicate_count += 1
                        print(f"⚠️ Skipping duplicate: {claim['unique_id']}")
                    else:
                        failed_claims.append({
                            "unique_id": claim['unique_id'],
                            "error": str(e)
                        })
        else:
            # Try batch insert (will fail on first duplicate)
            try:
                result = await db.insert_many_claims(claims_data)
                inserted_count = len(claims_data)
            except ValueError as e:
                # Extract info from error message
                error_msg = str(e)
                if "duplicate" in error_msg.lower():
                    raise HTTPException(
                        status_code=409,
                        detail=f"Duplicate claims detected. Use skip_duplicates=true to skip them. Error: {error_msg}"
                    )
                raise
        
        response_data = {
            "message": "Claims upload completed",
            "claims_count": len(claims_data),
            "inserted_count": inserted_count,
            "duplicate_count": duplicate_count,
            "skipped_rows": len(skipped_rows),
            "tenant_id": tenant_id,
            "filename": file.filename,
            "file_type": filename_lower.split('.')[-1].upper()
        }
        
        # Add details if there were issues
        if skipped_rows:
            response_data["skipped_row_details"] = skipped_rows[:10]  # First 10 only
        if failed_claims:
            response_data["failed_claims"] = failed_claims[:10]
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Upload failed: {str(e)}"
        )

# main.py - ADD these new endpoints after the existing delete endpoint

@app.delete("/claims/{tenant_id}/duplicates")
async def remove_duplicates(
    tenant_id: str,
    current_user: str = Depends(verify_token)
):
    """Remove duplicate claims for a tenant (keeps most recent)"""
    try:
        # Aggregate to find duplicates
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {
                "$group": {
                    "_id": "$unique_id",
                    "count": {"$sum": 1},
                    "docs": {"$push": "$_id"}
                }
            },
            {"$match": {"count": {"$gt": 1}}}
        ]
        
        cursor = db.database.claims_master.aggregate(pipeline)
        duplicates = await cursor.to_list(length=None)
        
        deleted_count = 0
        for dup in duplicates:
            # Keep the first one, delete the rest
            ids_to_delete = dup["docs"][1:]
            result = await db.database.claims_master.delete_many({
                "_id": {"$in": ids_to_delete}
            })
            deleted_count += result.deleted_count
        
        return {
            "message": "Duplicates removed",
            "tenant_id": tenant_id,
            "duplicate_groups": len(duplicates),
            "claims_deleted": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to remove duplicates: {str(e)}"
        )


@app.get("/claims/{tenant_id}/duplicates")
async def check_duplicates(
    tenant_id: str,
    current_user: str = Depends(verify_token)
):
    """Check for duplicate claims in a tenant"""
    try:
        # Aggregate to find duplicates
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {
                "$group": {
                    "_id": "$unique_id",
                    "count": {"$sum": 1},
                    "claim_ids": {"$push": "$claim_id"}
                }
            },
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        cursor = db.database.claims_master.aggregate(pipeline)
        duplicates = await cursor.to_list(length=100)  # Limit to 100
        
        return {
            "tenant_id": tenant_id,
            "duplicate_count": len(duplicates),
            "duplicates": duplicates
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to check duplicates: {str(e)}"
        )
        
# Quick fix - Add this temporary endpoint to main.py
@app.post("/debug/clear-claims/{tenant_id}")
async def debug_clear_claims(tenant_id: str):
    """DEBUG: Clear all claims for a tenant"""
    result = await db.database.claims_master.delete_many({"tenant_id": tenant_id})
    return {
        "deleted": result.deleted_count,
        "tenant_id": tenant_id
    }
    
    
# main.py - REPLACE /validate endpoint

@app.post("/validate")
async def validate_claims(
    tenant_id: str = Query(..., description="Tenant ID for validation"),
    current_user: str = Depends(verify_token)
):
    """Run validation pipeline on uploaded claims with accurate error reporting"""
    try:
        print(f"Validating claims for tenant: {tenant_id}")
        
        # Validate tenant_id
        if not tenant_id or tenant_id.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="tenant_id parameter is required and cannot be empty"
            )
        
        # Get tenant rules configuration
        rules_config = await db.get_rules_config(tenant_id)
        if not rules_config:
            raise HTTPException(
                status_code=404,
                detail=f"No rules configuration found for tenant: {tenant_id}"
            )
            
        print(f"Rules config found for tenant {tenant_id}")
        
        # Run validation pipeline
        validation_results = await validation_service.validate_tenant_claims(
            tenant_id, rules_config
        )
        
        # Generate analytics
        analytics_results = await analytics_service.generate_analytics(tenant_id)
        
        # Extract error summary from analytics
        error_summary = analytics_results.get("error_summary", {})
        
        return {
            "message": "Validation completed successfully",
            "tenant_id": tenant_id,
            "total_claims": validation_results["total_claims"],
            "validated_claims": validation_results["validated_claims"],
            "error_claims": validation_results["error_claims"],
            "processing_time": validation_results["processing_time"],
            "error_breakdown": {
                "technical_only": error_summary.get("technical_only", 0),
                "medical_only": error_summary.get("medical_only", 0),
                "both_errors": error_summary.get("both_errors", 0),
                "no_errors": error_summary.get("no_errors", 0),
                "total_errors": error_summary.get("total_errors", 0)
            },
            "summary": validation_results.get("summary", {}),
            "analytics": analytics_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Validation error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")






# @app.post("/validate")
# async def validate_claims(
#     tenant_id: str = Query("default", description="Tenant ID for validation"),  # Make it required
#     current_user: str = Depends(verify_token)
# ):
#     """Run validation pipeline on uploaded claims"""
#     try:
#         print(f"Validating claims for tenant: {tenant_id}")
        
#         # Validate tenant_id is not empty
#         if not tenant_id or tenant_id.strip() == "":
#             raise HTTPException(
#                 status_code=400,
#                 detail="tenant_id parameter is required and cannot be empty"
#             )
        
#         # Get tenant rules configuration
#         rules_config = await db.get_rules_config(tenant_id)
#         if not rules_config:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"No rules configuration found for tenant: {tenant_id}"
#             )
            
#         print(f"Rules config found for tenant {tenant_id}") # Debug log
        
#         # Run validation pipeline
#         validation_results = await validation_service.validate_tenant_claims(
#             tenant_id, rules_config
#         )
        
#         # Generate analytics
#         analytics_results = await analytics_service.generate_analytics(tenant_id)
        
#         return {
#             "message": "Validation completed successfully",
#             "tenant_id": tenant_id,
#             "total_claims": validation_results["total_claims"],
#             "validated_claims": validation_results["validated_claims"],
#             "error_claims": validation_results["error_claims"],
#             "analytics": analytics_results
#         }
        
#     except Exception as e:
#         print(f"Validation error: {str(e)}")  # Debug log
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

# main.py - ADD this debug endpoint temporarily

@app.get("/debug/claims/{tenant_id}")
async def debug_claims(
    tenant_id: str,
    current_user: str = Depends(verify_token)
):
    """Debug endpoint to see validation errors for each claim"""
    try:
        claims = await db.get_claims_by_tenant(tenant_id, skip=0, limit=100)
        
        debug_info = []
        for claim in claims:
            debug_info.append({
                "claim_id": claim.get("claim_id"),
                "unique_id": claim.get("unique_id"),
                "status": claim.get("status"),
                "error_type": claim.get("error_type"),
                "errors": claim.get("error_explanation", []),
                "national_id": claim.get("national_id"),
                "member_id": claim.get("member_id"),
                "facility_id": claim.get("facility_id"),
                "encounter_type": claim.get("encounter_type"),
                "service_code": claim.get("service_code"),
                "diagnosis_codes": claim.get("diagnosis_codes"),
                "paid_amount": claim.get("paid_amount_aed"),
                "approval_number": claim.get("approval_number")
            })
        
        return {
            "tenant_id": tenant_id,
            "total_claims": len(claims),
            "claims": debug_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/{tenant_id}")
async def get_results(
    tenant_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user: str = Depends(verify_token)
):
    """Get validation results for a tenant"""
    try:
        # Get paginated claims results
        claims = await db.get_claims_by_tenant(tenant_id, skip, limit)
        total_count = await db.count_claims_by_tenant(tenant_id)
        
        # Get analytics data
        analytics = await analytics_service.get_analytics_by_tenant(tenant_id)
        
        return {
            "claims": claims,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total_count,
                "has_next": skip + limit < total_count
            },
            "analytics": analytics
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")

@app.get("/analytics/{tenant_id}")
async def get_analytics(
    tenant_id: str,
    current_user: str = Depends(verify_token)
):
    """Get analytics data for charts"""
    try:
        analytics = await analytics_service.get_comprehensive_analytics(tenant_id)
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@app.delete("/claims/{tenant_id}")
async def clear_tenant_data(
    tenant_id: str,
    current_user: str = Depends(verify_token)
):
    """Clear all data for a tenant (for testing)"""
    try:
        await db.clear_tenant_data(tenant_id)
        return {"message": f"All data cleared for tenant: {tenant_id}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000)) 
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )