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



# In main.py, update the upload_claims endpoint:
@app.post("/upload/claims")
async def upload_claims(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    current_user: str = Depends(verify_token)
):
    """Upload and process claims file"""
    try:
        # Validate file type
        if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=400, 
                detail="Only CSV and Excel files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Parse file based on type
        if file.filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))
        
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
                detail=f"Missing required columns: {missing_columns}"
            )
        
        # Convert to records and store in master table
        claims_data = []
        for _, row in df.iterrows():
            claim = {
                "claim_id": str(row['claim_id']),
                "encounter_type": str(row['encounter_type']),
                "service_date": str(row['service_date']),
                "national_id": str(row['national_id']),
                "member_id": str(row['member_id']),
                "facility_id": str(row['facility_id']),
                "unique_id": str(row['unique_id']),
                "diagnosis_codes": str(row['diagnosis_codes']).split(',') if pd.notna(row['diagnosis_codes']) else [],
                "service_code": str(row['service_code']),
                "paid_amount_aed": float(row['paid_amount_aed']),
                "approval_number": str(row['approval_number']) if pd.notna(row['approval_number']) else "",
                "tenant_id": tenant_id,
                "uploaded_at": datetime.utcnow(),
                "status": "Pending",
                "error_type": "No error",
                "error_explanation": [],
                "recommended_action": ""
            }
            claims_data.append(claim)
        
        # Store in database - use claims collection
        result = await db.insert_many_claims(claims_data)
        
        return {
            "message": "Claims uploaded successfully",
            "claims_count": len(claims_data),
            "tenant_id": tenant_id,
            "inserted_ids": [str(id) for id in result.inserted_ids]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")





@app.post("/validate")
async def validate_claims(
    tenant_id: str = Query("default", description="Tenant ID for validation"),  # Make it required
    current_user: str = Depends(verify_token)
):
    """Run validation pipeline on uploaded claims"""
    try:
        print(f"Validating claims for tenant: {tenant_id}")
        
        # Validate tenant_id is not empty
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
            
        print(f"Rules config found for tenant {tenant_id}") # Debug log
        
        # Run validation pipeline
        validation_results = await validation_service.validate_tenant_claims(
            tenant_id, rules_config
        )
        
        # Generate analytics
        analytics_results = await analytics_service.generate_analytics(tenant_id)
        
        return {
            "message": "Validation completed successfully",
            "tenant_id": tenant_id,
            "total_claims": validation_results["total_claims"],
            "validated_claims": validation_results["validated_claims"],
            "error_claims": validation_results["error_claims"],
            "analytics": analytics_results
        }
        
    except Exception as e:
        print(f"Validation error: {str(e)}")  # Debug log
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")




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