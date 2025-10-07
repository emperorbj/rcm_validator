# models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

class EncounterType(str, Enum):
    INPATIENT = "INPATIENT"
    OUTPATIENT = "OUTPATIENT"

class StatusType(str, Enum):
    PENDING = "Pending"
    VALIDATED = "Validated"
    NOT_VALIDATED = "Not validated"

class ErrorType(str, Enum):
    NO_ERROR = "No error"
    MEDICAL_ERROR = "Medical error"
    TECHNICAL_ERROR = "Technical error"
    BOTH = "Both"

# Authentication Models
class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class UserResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

# Core Claim Model
class ClaimRecord(BaseModel):
    unique_id: str = Field(..., description="Unique claim identifier")
    encounter_type: EncounterType = Field(..., description="Type of medical encounter")
    service_date: str = Field(..., description="Date of service")
    national_id: str = Field(..., description="Patient national ID")
    member_id: str = Field(..., description="Member ID")
    facility_id: str = Field(..., description="Healthcare facility ID")
    unique_id: str = Field(..., description="Composite unique ID")
    diagnosis_codes: List[str] = Field(..., description="List of diagnosis codes")
    service_code: str = Field(..., description="Medical service code")
    paid_amount_aed: float = Field(..., ge=0, description="Amount paid in AED")
    approval_number: Optional[str] = Field(None, description="Prior approval number")
    
    # Validation results (populated after processing)
    tenant_id: Optional[str] = Field("default", description="Tenant identifier")
    status: StatusType = Field(StatusType.PENDING, description="Validation status")
    error_type: ErrorType = Field(ErrorType.NO_ERROR, description="Type of error found")
    error_explanation: List[str] = Field([], description="Detailed error explanations")
    recommended_action: str = Field("", description="Recommended corrective action")
    
    # Metadata
    uploaded_at: Optional[datetime] = Field(None, description="Upload timestamp")
    validated_at: Optional[datetime] = Field(None, description="Validation timestamp")
    
    @validator('unique_id')
    def validate_unique_id_format(cls, v):
        """Validate unique_id follows the pattern: XXXX-XXXX-XXXX"""
        parts = v.split('-')
        if len(parts) != 3:
            raise ValueError('unique_id must have format XXXX-XXXX-XXXX')
        if not all(len(part) == 4 for part in parts):
            raise ValueError('Each segment of unique_id must be 4 characters')
        if not all(part.isalnum() and part.isupper() for part in parts):
            raise ValueError('unique_id segments must be uppercase alphanumeric')
        return v
    
    @validator('diagnosis_codes')
    def validate_diagnosis_codes(cls, v):
        """Ensure diagnosis codes are properly formatted"""
        if not v:
            return []
        # Remove empty strings and strip whitespace
        return [code.strip() for code in v if code.strip()]

class ValidationResult(BaseModel):
    unique_id: str
    status: StatusType
    error_type: ErrorType
    error_explanation: List[str]
    recommended_action: str
    technical_errors: List[str] = []
    medical_errors: List[str] = []

# Request/Response Models
class ValidationRequest(BaseModel):
    tenant_id: str = "default"
    unique_ids: Optional[List[str]] = None  # If None, validate all pending claims

class ValidationResponse(BaseModel):
    message: str
    tenant_id: str
    total_claims: int
    validated_claims: int
    error_claims: int
    processing_time_seconds: float
    summary: Dict[str, int]

class AnalyticsData(BaseModel):
    error_category: str
    claim_count: int
    total_paid_amount: float
    percentage: Optional[float] = None

class ChartData(BaseModel):
    category: str
    value: float
    count: int

class AnalyticsResponse(BaseModel):
    tenant_id: str
    total_claims: int
    validation_summary: Dict[str, int]
    error_distribution: List[AnalyticsData]
    claims_by_error_chart: List[ChartData]
    amounts_by_error_chart: List[ChartData]
    generated_at: datetime

# Rules Configuration Models
class TechnicalRule(BaseModel):
    service_code: str
    description: str
    approval_required: bool
    paid_amount_threshold: Optional[float] = None

class MedicalRule(BaseModel):
    rule_type: str  # "encounter_type", "facility_type", "diagnosis_required", "mutually_exclusive"
    conditions: Dict[str, Any]
    description: str

class RulesConfiguration(BaseModel):
    tenant_id: str
    technical_rules: List[TechnicalRule] = []
    medical_rules: List[MedicalRule] = []
    paid_amount_threshold: float = 250.0
    facility_registry: Dict[str, str] = {}
    uploaded_at: datetime
    
class RuleUploadRequest(BaseModel):
    tenant_id: str = "default"
    technical_rules_content: Optional[str] = None
    medical_rules_content: Optional[str] = None

# File Upload Models
class FileUploadResponse(BaseModel):
    message: str
    filename: str
    size_bytes: int
    tenant_id: str
    processed_records: int

# Error Models
class ValidationError(BaseModel):
    error_type: str
    field: Optional[str] = None
    message: str
    rule_violated: Optional[str] = None

class APIError(BaseModel):
    error: str
    detail: str
    timestamp: datetime
    path: Optional[str] = None

# Pagination Models
class PaginationParams(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_previous: bool

# Search and Filter Models
class ClaimFilter(BaseModel):
    tenant_id: str
    status: Optional[StatusType] = None
    error_type: Optional[ErrorType] = None
    encounter_type: Optional[EncounterType] = None
    facility_id: Optional[str] = None
    service_code: Optional[str] = None
    min_paid_amount: Optional[float] = None
    max_paid_amount: Optional[float] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class ClaimSearchRequest(BaseModel):
    filters: ClaimFilter
    pagination: PaginationParams = PaginationParams()
    sort_by: str = "uploaded_at"
    sort_order: str = "desc"  # "asc" or "desc"

# Health Check Models
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database: str
    version: str
    uptime_seconds: Optional[float] = None

# Configuration Models
class AppSettings(BaseModel):
    mongodb_uri: str
    secret_key: str
    openai_api_key: Optional[str] = None
    pinecone_api_key: Optional[str] = None
    environment: str = "development"
    debug: bool = True
    cors_origins: List[str] = ["*"]

# LLM Evaluation Models
class LLMEvaluationRequest(BaseModel):
    claim_data: ClaimRecord
    rules_context: str
    evaluation_type: str  # "medical" or "technical"

class LLMEvaluationResponse(BaseModel):
    unique_id: str
    evaluation_type: str
    has_errors: bool
    errors_found: List[str]
    explanation: str
    confidence_score: float
    recommended_action: str

# Metrics and Reporting Models
class MetricsData(BaseModel):
    tenant_id: str
    date: datetime
    total_claims_processed: int
    validation_errors_found: int
    technical_errors: int
    medical_errors: int
    total_paid_amount: float
    average_processing_time: float

class ReportRequest(BaseModel):
    tenant_id: str
    date_from: datetime
    date_to: datetime
    include_detailed_errors: bool = False
    export_format: str = "json"  # "json", "csv", "excel"

# Tenant Management Models
class TenantInfo(BaseModel):
    tenant_id: str
    tenant_name: str
    created_at: datetime
    active: bool = True
    configuration: Dict[str, Any] = {}

class TenantStats(BaseModel):
    tenant_id: str
    total_claims: int
    total_validations: int
    error_rate: float
    last_activity: Optional[datetime] = None