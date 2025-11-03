# services/validation_service.py
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pymongo import UpdateOne
from datetime import datetime
import json
import re
from database.mongodb import MongoDB
from services.rule_engine import RuleEngine
from services.llm_service import LLMService
from models.schemas import ClaimRecord, ValidationResult, ErrorType, StatusType
import logging

# Add after imports
logger = logging.getLogger(__name__)
class ValidationService:
    def __init__(self, db: MongoDB, rule_engine: RuleEngine):
        self.db = db
        self.rule_engine = rule_engine
        self.llm_service = LLMService()
    
    def _normalize_unique_id(self, uid: str) -> str:
        """Convert lowercase or no-hyphen IDs to the required format."""
        if not uid:
            return uid
        uid = uid.upper().replace('-', '')
        if len(uid) == 12:
            return f"{uid[0:4]}-{uid[4:8]}-{uid[8:12]}"
        return uid
    
    # services/validation_service.py - REPLACE the validate_tenant_claims method

    async def validate_tenant_claims(
        self, 
        tenant_id: str, 
        rules_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run complete validation pipeline for a tenant"""
        start_time = time.time()
        
        try:
            # Load rules into rule engine
            await self._load_tenant_rules(rules_config)
            
            # Get pending claims for validation
            pending_claims = await self.db.get_pending_claims(tenant_id)
            
            if not pending_claims:
                return {
                    "total_claims": 0,
                    "validated_claims": 0,
                    "error_claims": 0,
                    "processing_time": 0.0,  # Added
                    "message": "No pending claims found",
                    "summary": {
                        "total": 0,
                        "validated": 0,
                        "not_validated": 0,
                        "no_error": 0,
                        "technical_error": 0,
                        "medical_error": 0,
                        "both_errors": 0
                    }
                }
            
            # Process claims in batches for better performance
            batch_size = 10
            validation_results = []
            
            for i in range(0, len(pending_claims), batch_size):
                batch = pending_claims[i:i + batch_size]
                batch_results = await self._process_claims_batch(batch, rules_config)
                validation_results.extend(batch_results)
            
            # Update database with results
            await self._update_claims_with_results(validation_results, tenant_id)
            
            # Calculate summary statistics
            total_claims = len(validation_results)
            validated_claims = sum(1 for r in validation_results if r.status == StatusType.VALIDATED)
            error_claims = total_claims - validated_claims
            processing_time = time.time() - start_time
            
            return {
                "total_claims": total_claims,
                "validated_claims": validated_claims,
                "error_claims": error_claims,
                "processing_time": round(processing_time, 2),  # Added - rounded to 2 decimals
                "summary": self._generate_validation_summary(validation_results)
            }
        
        except Exception as e:
            print(f"Error in validate_tenant_claims: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
    
    # async def validate_tenant_claims(
    #     self, 
    #     tenant_id: str, 
    #     rules_config: Dict[str, Any]
    # ) -> Dict[str, Any]:
    #     """Run complete validation pipeline for a tenant"""
    #     start_time = time.time()
        
    #     try:
    #         # Load rules into rule engine
    #         await self._load_tenant_rules(rules_config)
            
    #         # Get pending claims for validation
    #         pending_claims = await self.db.get_pending_claims(tenant_id)
            
    #         if not pending_claims:
    #             return {
    #                 "total_claims": 0,
    #                 "validated_claims": 0,
    #                 "error_claims": 0,
    #                 "processing_time": 0,
    #                 "message": "No pending claims found"
    #             }
            
    #         # Process claims in batches for better performance
    #         batch_size = 10
    #         validation_results = []
            
    #         for i in range(0, len(pending_claims), batch_size):
    #             batch = pending_claims[i:i + batch_size]
    #             batch_results = await self._process_claims_batch(batch, rules_config)
    #             validation_results.extend(batch_results)
            
    #         # Update database with results
    #         await self._update_claims_with_results(validation_results, tenant_id)
            
    #         # Calculate summary statistics
    #         total_claims = len(validation_results)
    #         validated_claims = sum(1 for r in validation_results if r.status == StatusType.VALIDATED)
    #         error_claims = total_claims - validated_claims
    #         processing_time = time.time() - start_time
            
    #         summary = self._generate_validation_summary(validation_results)

    #         return {
    #             "message": f"Validation completed for {tenant_id}",
    #             "tenant_id": tenant_id,
    #             "total_claims": total_claims,
    #             "validated_claims": validated_claims,
    #             "error_claims": error_claims,
    #             "processing_time_seconds": processing_time,
    #             "summary": summary,
    #             # Add synthesized report as requested in feedback
    #             "synthesized_report": {
    #                 "total_claims": summary["total"],
    #                 "claims_with_no_errors": summary["no_error"],
    #                 "technical_errors_only": summary["technical_error_only"],
    #                 "medical_errors_only": summary["medical_error_only"],
    #                 "both_errors": summary["both_errors"],
    #                 "total_claims_with_errors": summary["total_with_errors"],
    #                 "error_rate": f"{summary['error_rate_percentage']}%",
    #                 "validation_success_rate": f"{summary['validation_success_rate']}%"
    #             }
    #         }
            
    #         # return {
    #         #     "total_claims": total_claims,
    #         #     "validated_claims": validated_claims,
    #         #     "error_claims": error_claims,
    #         #     "processing_time": processing_time,
    #         #     "summary": self._generate_validation_summary(validation_results)
    #         # }
        
    #     except Exception as e:
    #         print(f"Error in validate_tenant_claims: {str(e)}")
    #         import traceback
    #         traceback.print_exc()
    #         raise e

    async def _load_tenant_rules(self, rules_config: Dict[str, Any]):
        """Load and parse rules for the tenant"""
        try:
            # Parse technical rules
            if "technical_rules" in rules_config:
                self.rule_engine.parse_technical_rules(rules_config["technical_rules"])
            
            # Parse medical rules
            if "medical_rules" in rules_config:
                self.rule_engine.parse_medical_rules(rules_config["medical_rules"])
            
        except Exception as e:
            raise ValueError(f"Failed to load tenant rules: {str(e)}")
    
    async def _process_claims_batch(
        self, 
        claims_batch: List[Dict[str, Any]], 
        rules_config: Dict[str, Any]
    ) -> List[ValidationResult]:
        """Process a batch of claims with both static and LLM validation"""
        results = []
        
        for claim_data in claims_batch:
            try:
                # Convert to ClaimRecord object
                claim = self._dict_to_claim_record(claim_data)
                logger.info(f"Validating claim {claim.unique_id} | Tenant: {claim.tenant_id} | "
                    f"Encounter: {claim.encounter_type} | Service: {claim.service_code}")
                
                # Run static rule validation
                static_result = self.rule_engine.validate_claim(claim)
                
                logger.info(f"Claim {claim.unique_id} | Status: {static_result.status.value} | "
                    f"Error Type: {static_result.error_type.value} | "
                    f"Errors Found: {len(static_result.error_explanation)}")
                
                # Run LLM-based validation for additional insights
                # llm_result = await self._run_llm_validation(claim, rules_config)
                
                # # Combine results
                # combined_result = self._combine_validation_results(
                #     static_result, llm_result, claim
                # )
                
                use_llm = True  # Change to True only if you want AI insights

                if use_llm:
                    llm_result = await self._run_llm_validation(claim, rules_config)
                    # Use LLM only to enhance explanations, not to add new errors
                    if llm_result.get("enhanced_explanation"):
                        static_result.error_explanation.append(
                            f"AI Insight: {llm_result['enhanced_explanation']}"
                        )
                    combined_result = static_result
                else:
                    # Pure static validation (deterministic)
                    combined_result = static_result
                
                results.append(combined_result)
                
            except Exception as e:
                print(f"Error processing claim {claim_data.get('unique_id', 'unknown')}: {str(e)}")
                # Create a failed validation result
                results.append(ValidationResult(
                    unique_id=str(claim_data.get('unique_id', 'unknown')),
                    status=StatusType.NOT_VALIDATED,
                    error_type=ErrorType.TECHNICAL_ERROR,
                    error_explanation=[f"Processing error: {str(e)}"],
                    recommended_action="Review claim data format",
                    technical_errors=[f"Processing error: {str(e)}"],
                    medical_errors=[]
                ))
        
        return results
    
    async def _run_llm_validation(
        self, 
        claim: ClaimRecord, 
        rules_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run LLM-based validation for nuanced rule checking"""
        try:
            # Prepare context for LLM
            rules_context = self._prepare_rules_context(rules_config)
            claim_context = self._prepare_claim_context(claim)
            
            # Get LLM evaluation
            llm_response = await self.llm_service.evaluate_claim(
                claim_context, rules_context
            )
            
            return llm_response
            
        except Exception as e:
            print(f"LLM validation failed for claim {claim.unique_id}: {str(e)}")
            # Return empty result if LLM fails
            return {
                "has_additional_errors": False,
                "additional_errors": [],
                "enhanced_explanation": "",
                "confidence_score": 0.0
            }
    
    def _prepare_rules_context(self, rules_config: Dict[str, Any]) -> str:
        """Prepare rules context for LLM evaluation"""
        context_parts = []
        
        # Add technical rules summary
        if "technical_rules" in rules_config:
            context_parts.append("TECHNICAL RULES:")
            context_parts.append("- Services requiring prior approval: SRV1001, SRV1002, SRV2008")
            context_parts.append("- Diagnoses requiring prior approval: E11.9, R07.9, Z34.0")
            context_parts.append("- Paid amount threshold: AED 250")
            context_parts.append("- ID format must be uppercase alphanumeric with pattern XXXX-XXXX-XXXX")
        
        # Add medical rules summary
        if "medical_rules" in rules_config:
            context_parts.append("\nMEDICAL RULES:")
            context_parts.append("- Inpatient-only: SRV1001, SRV1002, SRV1003")
            context_parts.append("- Outpatient-only: SRV2001-SRV2011")
            context_parts.append("- Facility constraints apply")
            context_parts.append("- Diagnosis-service matching required")
            context_parts.append("- Mutually exclusive diagnoses: R73.03+E11.9, E66.9+E66.3, R51+G43.9")
        
        return "\n".join(context_parts)
    
    def _prepare_claim_context(self, claim: ClaimRecord) -> str:
        """Prepare claim context for LLM evaluation"""
        return f"""
CLAIM DETAILS:
- Claim ID: {claim.unique_id}
- Encounter Type: {claim.encounter_type}
- Service Code: {claim.service_code}
- Diagnosis Codes: {', '.join(claim.diagnosis_codes)}
- Facility ID: {claim.facility_id}
- Paid Amount: AED {claim.paid_amount_aed}
- Approval Number: {claim.approval_number or 'None'}
- Unique ID: {claim.unique_id}
- National ID: {claim.national_id}
- Member ID: {claim.member_id}
        """.strip()
    
    def _combine_validation_results(
        self, 
        static_result: ValidationResult, 
        llm_result: Dict[str, Any],
        claim: ClaimRecord
    ) -> ValidationResult:
        """Combine static and LLM validation results"""
        # Start with static result
        combined_errors = static_result.error_explanation.copy()
        
        # Add LLM insights if available
        if llm_result.get("has_additional_errors", False):
            additional_errors = llm_result.get("additional_errors", [])
            combined_errors.extend(additional_errors)
        
        # Enhance explanation with LLM insights
        enhanced_explanation = llm_result.get("enhanced_explanation", "")
        if enhanced_explanation:
            combined_errors.append(f"Additional insight: {enhanced_explanation}")
        
        # Determine final status
        # final_status = static_result.status
        # final_error_type = static_result.error_type
        
        # if combined_errors and final_status == StatusType.VALIDATED:
        #     final_status = StatusType.NOT_VALIDATED
        #     final_error_type = ErrorType.BOTH  # Assume both if LLM found additional issues
        
        
        
        all_technical_errors = static_result.technical_errors.copy()
        all_medical_errors = static_result.medical_errors.copy()

# Add LLM errors to appropriate category if available
        if llm_result.get("has_additional_errors", False):
            llm_errors = llm_result.get("additional_errors", [])
            # Simple categorization: check if error mentions approval/threshold/format = technical
            for error in llm_errors:
                error_lower = error.lower()
                if any(keyword in error_lower for keyword in ["approval", "threshold", "format", "id", "amount"]):
                    all_technical_errors.append(error)
                else:
                    all_medical_errors.append(error)

        # Correctly categorize based on actual errors present
        if all_technical_errors and all_medical_errors:
            final_error_type = ErrorType.BOTH
            final_status = StatusType.NOT_VALIDATED
        elif all_technical_errors:
            final_error_type = ErrorType.TECHNICAL_ERROR
            final_status = StatusType.NOT_VALIDATED
        elif all_medical_errors:
            final_error_type = ErrorType.MEDICAL_ERROR
            final_status = StatusType.NOT_VALIDATED
        else:
            final_error_type = ErrorType.NO_ERROR
            final_status = StatusType.VALIDATED

        # Update combined errors list
        combined_errors = all_technical_errors + all_medical_errors
        
        # Update recommended action if needed
        recommended_action = static_result.recommended_action
        if llm_result.get("recommended_action"):
            recommended_action += f"; {llm_result['recommended_action']}"
        
        return ValidationResult(
            unique_id=claim.unique_id,
            status=final_status,
            error_type=final_error_type,
            error_explanation=combined_errors,
            recommended_action=recommended_action,
            technical_errors=static_result.technical_errors,
            medical_errors=static_result.medical_errors
        )
    
    async def _update_claims_with_results(self, validation_results: List[ValidationResult], tenant_id: str):
        """Bulk update claims with validation results"""
        operations = []
        for result in validation_results:
            operations.append(
                UpdateOne(
                    {"unique_id": result.unique_id, "tenant_id": tenant_id},
                    {
                        "$set": {
                            "status": result.status.value,
                            "error_type": result.error_type.value,
                            "error_explanation": result.error_explanation,
                            "recommended_action": result.recommended_action,
                            "validated_at": datetime.utcnow()
                        }
                    },
                    upsert=False
                )
            )
        if operations:
        # Fix: Use self.db.database.claims_master instead of self.db.claims
            result = await self.db.database.claims_master.bulk_write(operations)
            print(f"Updated {result.modified_count} claims with validation results")
            return result
        print("No operations to perform for claims update")
        return None


        
        # services/validation_service.py - REPLACE _dict_to_claim_record method
# Replace the _dict_to_claim_record method in services/validation_service.py

    def _dict_to_claim_record(self, claim_dict: dict) -> ClaimRecord:
        """Convert a raw MongoDB claim document (dict) into a ClaimRecord model."""
        try:
            # ✅ FIX: Remove normalization since it's done at upload time
            # Data from DB is already in correct format
            unique_id = str(claim_dict.get("unique_id", ""))
            
            # Ensure diagnosis_codes is a list
            diagnosis_codes = claim_dict.get("diagnosis_codes", [])
            if isinstance(diagnosis_codes, str):
                # Handle both semicolon and comma separators (legacy data)
                diagnosis_codes = [
                    code.strip().upper()
                    for code in diagnosis_codes.replace(';', ',').split(',') 
                    if code.strip()
                ]
            
            # Normalize approval_number (handle various "NA" representations)
            approval_number = claim_dict.get("approval_number", "")
            if approval_number and approval_number.upper() in ["NA", "N/A", "NONE", "NULL", "NAN"]:
                approval_number = ""
            
            return ClaimRecord(
                unique_id=unique_id,  # ✅ Already normalized in DB
                encounter_type=claim_dict.get("encounter_type"),
                service_date=claim_dict.get("service_date"),
                national_id=str(claim_dict.get("national_id", "")),  # ✅ Already uppercase in DB
                member_id=str(claim_dict.get("member_id", "")),  # ✅ Already uppercase in DB
                facility_id=str(claim_dict.get("facility_id", "")),  # ✅ Already uppercase in DB
                diagnosis_codes=diagnosis_codes,  # ✅ Already uppercase in DB
                service_code=claim_dict.get("service_code"),  # ✅ Already uppercase in DB
                paid_amount_aed=float(claim_dict.get("paid_amount_aed", 0)),
                approval_number=approval_number
            )
        except Exception as e:
            print(f"❌ Error converting claim dict to ClaimRecord: {str(e)}")
            print(f"Claim dict: {claim_dict}")
            raise e

# services/validation_service.py - REPLACE _generate_validation_summary method

    def _generate_validation_summary(self, validation_results: List[ValidationResult]) -> Dict[str, Any]:
        """Generate summary statistics from validation results"""
        total = len(validation_results)
        
        # Count by status
        validated = sum(1 for r in validation_results if r.status == StatusType.VALIDATED)
        not_validated = sum(1 for r in validation_results if r.status == StatusType.NOT_VALIDATED)
        
        # Count by error type
        no_error = sum(1 for r in validation_results if r.error_type == ErrorType.NO_ERROR)
        technical_only = sum(1 for r in validation_results if r.error_type == ErrorType.TECHNICAL_ERROR)
        medical_only = sum(1 for r in validation_results if r.error_type == ErrorType.MEDICAL_ERROR)
        both_errors = sum(1 for r in validation_results if r.error_type == ErrorType.BOTH)
        
        # Calculate totals
        total_with_errors = technical_only + medical_only + both_errors
        error_rate = (total_with_errors / total * 100) if total > 0 else 0.0
        validation_success_rate = (validated / total * 100) if total > 0 else 0.0
        
        return {
            "total": total,
            "validated": validated,
            "not_validated": not_validated,
            "no_error": no_error,
            "technical_error_only": technical_only,
            "medical_error_only": medical_only,
            "both_errors": both_errors,
            "total_with_errors": total_with_errors,
            "error_rate_percentage": round(error_rate, 2),
            "validation_success_rate": round(validation_success_rate, 2)
        }
    # def _generate_validation_summary(self, validation_results: List[ValidationResult]) -> Dict[str, int]:
    #     """Generate summary statistics from validation results"""
    #     summary = {
    #         "total": len(validation_results),
    #         "validated": 0,
    #         "not_validated": 0,
    #         "no_error": 0,
    #         "technical_error": 0,
    #         "medical_error": 0,
    #         "both_errors": 0
    #     }
        
    #     for result in validation_results:
    #         if result.status == StatusType.VALIDATED:
    #             summary["validated"] += 1
    #             summary["no_error"] += 1
    #         else:
    #             summary["not_validated"] += 1
    #             if result.error_type == ErrorType.TECHNICAL_ERROR:
    #                 summary["technical_error"] += 1
    #             elif result.error_type == ErrorType.MEDICAL_ERROR:
    #                 summary["medical_error"] += 1
    #             elif result.error_type == ErrorType.BOTH:
    #                 summary["both_errors"] += 1
    #     return summary
    
    # def _generate_validation_summary(self, validation_results: List[ValidationResult]) -> Dict[str, int]:
        """
        Generate summary statistics from validation results - ENHANCED VERSION
        """
        total = len(validation_results)
        validated = sum(1 for r in validation_results if r.status == StatusType.VALIDATED)
        
        # Count by error type
        technical_only = sum(
            1 for r in validation_results 
            if r.error_type == ErrorType.TECHNICAL_ERROR
        )
        
        medical_only = sum(
            1 for r in validation_results 
            if r.error_type == ErrorType.MEDICAL_ERROR
        )
        
        both_errors = sum(
            1 for r in validation_results 
            if r.error_type == ErrorType.BOTH
        )
        
        no_error = sum(
            1 for r in validation_results 
            if r.error_type == ErrorType.NO_ERROR
        )
        
        total_with_errors = technical_only + medical_only + both_errors
        
        return {
            "total": total,
            "validated": validated,
            "not_validated": total - validated,
            "no_error": no_error,
            "technical_error_only": technical_only,
            "medical_error_only": medical_only,
            "both_errors": both_errors,
            "total_with_errors": total_with_errors,
            # Additional metrics
            "error_rate_percentage": round((total_with_errors / total * 100), 2) if total > 0 else 0,
            "validation_success_rate": round((validated / total * 100), 2) if total > 0 else 0
        }