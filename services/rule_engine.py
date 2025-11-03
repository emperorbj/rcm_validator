# services/rule_engine.py
import re
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from models.schemas import ClaimRecord, ValidationResult, ErrorType, StatusType

@dataclass
class TechnicalRuleConfig:
    services_requiring_approval: Dict[str, bool]
    diagnosis_requiring_approval: Dict[str, bool]
    paid_amount_threshold: float
    id_format_rules: Dict[str, Any]

@dataclass
class MedicalRuleConfig:
    inpatient_only_services: List[str]
    outpatient_only_services: List[str]
    facility_service_mapping: Dict[str, List[str]]
    facility_registry: Dict[str, str]
    diagnosis_service_requirements: Dict[str, List[str]]
    mutually_exclusive_diagnoses: List[Tuple[str, str]]

class RuleEngine:
    def __init__(self):
        self.technical_rules: Optional[TechnicalRuleConfig] = None
        self.medical_rules: Optional[MedicalRuleConfig] = None
        
    def parse_technical_rules(self, rules_content: str) -> TechnicalRuleConfig:
        """Parse technical rules from document content"""
        try:
            # Parse services requiring approval
            services_requiring_approval = {
                "SRV1001": True,  # Major Surgery
                "SRV1002": True,  # ICU Stay
                "SRV1003": False, # Inpatient Dialysis
                "SRV2001": False, # ECG
                "SRV2002": False, # Flu Vaccine
                "SRV2003": False, # Routine Lab Panel
                "SRV2004": False, # X-Ray
                "SRV2006": False, # Pulmonary Function Test
                "SRV2007": False, # HbA1c Test
                "SRV2008": True,  # Ultrasonogram – Pregnancy Check
                "SRV2010": False, # Outpatient Dialysis
                "SRV2011": False, # Cardiac Stress Test
            }
            
            # Parse diagnosis codes requiring approval
            diagnosis_requiring_approval = {
                "E11.9": True,   # Diabetes Mellitus
                "E66.3": False,  # Overweight
                "E66.9": False,  # Obesity
                "E88.9": False,  # Metabolic Disorder
                "G43.9": False,  # Migraine
                "J45.909": False, # Asthma
                "N39.0": False,  # Urinary Tract Infection
                "R07.9": True,   # Chest Pain
                "R51": False,    # Headache
                "R73.03": False, # Prediabetes
                "Z34.0": True,   # Pregnancy
            }
            
            # ID formatting rules
            id_format_rules = {
                "pattern": r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$",
                "segments": 3,
                "segment_length": 4,
                "allowed_chars": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            }
            
            config = TechnicalRuleConfig(
                services_requiring_approval=services_requiring_approval,
                diagnosis_requiring_approval=diagnosis_requiring_approval,
                paid_amount_threshold=250.0,  # AED 250
                id_format_rules=id_format_rules
            )
            
            self.technical_rules = config
            return config
            
        except Exception as e:
            raise ValueError(f"Failed to parse technical rules: {str(e)}")
    
    def parse_medical_rules(self, rules_content: str) -> MedicalRuleConfig:
        """Parse medical rules from document content"""
        try:
            # Inpatient-only services
            inpatient_only_services = [
                "SRV1001",  # Major Surgery
                "SRV1002",  # ICU Stay
                "SRV1003",  # Inpatient Dialysis
            ]
            
            # Outpatient-only services
            outpatient_only_services = [
                "SRV2001",  # ECG
                "SRV2002",  # Flu Vaccine
                "SRV2003",  # Routine Lab Panel
                "SRV2004",  # X-Ray
                "SRV2005",  # Urine Culture (FIXED - was missing)
                "SRV2006",  # Pulmonary Function Test
                "SRV2007",  # HbA1c Test
                "SRV2008",  # Ultrasonogram – Pregnancy Check
                "SRV2010",  # Outpatient Dialysis
                "SRV2011",  # Cardiac Stress Test
            ]

            # Facility registry
            facility_registry = {
                "0DBYE6KP": "DIALYSIS_CENTER",
                "2XKSZK4T": "MATERNITY_HOSPITAL",
                "7R1VMIGX": "CARDIOLOGY_CENTER",
                "96GUDLMT": "GENERAL_HOSPITAL",
                "9V7HTI6E": "GENERAL_HOSPITAL",
                "EGVP0QAQ": "GENERAL_HOSPITAL",
                "EPRETQTL": "DIALYSIS_CENTER",
                "FLXFBIMD": "GENERAL_HOSPITAL",
                "GLCTDQAJ": "MATERNITY_HOSPITAL",
                "GY0GUI8G": "GENERAL_HOSPITAL",
                "I2MFYKYM": "GENERAL_HOSPITAL",
                "LB7I54Z7": "CARDIOLOGY_CENTER",
                "M1XCZVQD": "CARDIOLOGY_CENTER",
                "M7DJYNG5": "GENERAL_HOSPITAL",
                "MT5W4HIR": "MATERNITY_HOSPITAL",
                "OCQUMGDW": "GENERAL_HOSPITAL",
                "OIAP2DTP": "CARDIOLOGY_CENTER",
                "Q3G9N34N": "GENERAL_HOSPITAL",
                "Q8OZ5Z7C": "GENERAL_HOSPITAL",
                "RNPGDXCU": "MATERNITY_HOSPITAL",
                "S174K5QK": "GENERAL_HOSPITAL",
                "SKH7D31V": "CARDIOLOGY_CENTER",
                "SZC62NTW": "GENERAL_HOSPITAL",
                "VV1GS6P0": "MATERNITY_HOSPITAL",
                "ZDE6M6NJ": "GENERAL_HOSPITAL",
            }
            
            # Facility-service mapping
            facility_service_mapping = {
                "MATERNITY_HOSPITAL": ["SRV2008"],
                "DIALYSIS_CENTER": ["SRV1003", "SRV2010"],
                "CARDIOLOGY_CENTER": ["SRV2001", "SRV2011"],
                "GENERAL_HOSPITAL": [
                    "SRV1001", "SRV1002", "SRV1003", "SRV2001", "SRV2002",
                    "SRV2003", "SRV2004", "SRV2006", "SRV2007", "SRV2008",
                    "SRV2010", "SRV2011"
                ]
            }
            
            # Diagnosis-service requirements
            diagnosis_service_requirements = {
                "E11.9": ["SRV2007"],  # Diabetes → HbA1c Test
                "J45.909": ["SRV2006"], # Asthma → Pulmonary Function Test
                "R07.9": ["SRV2001"],  # Chest Pain → ECG
                "Z34.0": ["SRV2008"],  # Pregnancy → Ultrasonogram
                "N39.0": ["SRV2005"],  # UTI → Urine Culture
            }
            
            # Mutually exclusive diagnoses
            mutually_exclusive_diagnoses = [
                ("R73.03", "E11.9"),   # Prediabetes vs Diabetes
                ("E66.9", "E66.3"),    # Obesity vs Overweight
                ("R51", "G43.9"),      # Headache vs Migraine
            ]
            
            config = MedicalRuleConfig(
                inpatient_only_services=inpatient_only_services,
                outpatient_only_services=outpatient_only_services,
                facility_service_mapping=facility_service_mapping,
                facility_registry=facility_registry,
                diagnosis_service_requirements=diagnosis_service_requirements,
                mutually_exclusive_diagnoses=mutually_exclusive_diagnoses
            )
            
            self.medical_rules = config
            return config
            
        except Exception as e:
            raise ValueError(f"Failed to parse medical rules: {str(e)}")
        
        # services/rule_engine.py - REPLACE validate_claim method

    def validate_claim(self, claim: ClaimRecord) -> ValidationResult:
        """Validate a single claim against all rules"""
        technical_errors = []
        medical_errors = []
        
        # Run technical validation
        if self.technical_rules:
            tech_errors = self._validate_technical_rules(claim)
            technical_errors.extend(tech_errors)
        
        # Run medical validation
        if self.medical_rules:
            med_errors = self._validate_medical_rules(claim)
            medical_errors.extend(med_errors)
        
        # Combine all errors
        all_errors = technical_errors + medical_errors
        
        # Determine status and error type
        if not all_errors or len(all_errors) == 0:
            # No errors found - claim is validated
            status = StatusType.VALIDATED
            error_type = ErrorType.NO_ERROR
            recommended_action = "No action required - claim is valid"
        else:
            # Errors found - claim is not validated
            status = StatusType.NOT_VALIDATED
            
            # Determine error type based on which lists have errors
            if technical_errors and medical_errors:
                error_type = ErrorType.BOTH
            elif technical_errors:
                error_type = ErrorType.TECHNICAL_ERROR
            elif medical_errors:
                error_type = ErrorType.MEDICAL_ERROR
            else:
                # Fallback (should not reach here)
                error_type = ErrorType.NO_ERROR
            
            recommended_action = self._generate_recommended_action(
                technical_errors, medical_errors, claim
            )
        
        return ValidationResult(
            unique_id=claim.unique_id,
            status=status,
            error_type=error_type,
            error_explanation=all_errors,
            recommended_action=recommended_action,
            technical_errors=technical_errors,
            medical_errors=medical_errors
        )
    

    # services/rule_engine.py - REPLACE _validate_technical_rules method

# services/rule_engine.py - REPLACE _validate_technical_rules method
# PRODUCTION: Strict approval validation

    def _validate_technical_rules(self, claim: ClaimRecord) -> List[str]:
        """Validate technical rules for a claim - STRICT PRODUCTION VERSION"""
        errors = []
        rules = self.technical_rules
        
        # Helper function to check if approval is valid
        def has_valid_approval(approval_str: str) -> bool:
            if not approval_str or approval_str.strip() == "":
                return False
            # Normalize and check against invalid values
            normalized = approval_str.strip().upper()
            invalid_values = ["NA", "N/A", "NONE", "NULL", "OBTAIN APPROVAL", "PENDING"]
            return normalized not in invalid_values
        
        # Track all reasons approval is needed
        approval_reasons = []
        
        # 1. Check service approval requirements
        if claim.service_code in rules.services_requiring_approval:
            if rules.services_requiring_approval[claim.service_code]:
                approval_reasons.append(f"service {claim.service_code}")
        
        # 2. Check diagnosis approval requirements  
        for diagnosis in claim.diagnosis_codes:
            if diagnosis in rules.diagnosis_requiring_approval:
                if rules.diagnosis_requiring_approval[diagnosis]:
                    approval_reasons.append(f"diagnosis {diagnosis}")
        
        # 3. Check paid amount threshold
        if claim.paid_amount_aed > rules.paid_amount_threshold:
            approval_reasons.append(f"paid amount AED {claim.paid_amount_aed:.2f} (exceeds threshold of AED {rules.paid_amount_threshold})")
        
        # If approval is required but not provided, add error for EACH reason
        if approval_reasons:
            if not has_valid_approval(claim.approval_number):
                for reason in approval_reasons:
                    errors.append(
                        f"Technical Error: Prior approval required for {reason}, but no valid approval number provided (got: '{claim.approval_number or 'empty'}')"
                    )
        
        # 4. Validate ID formatting (call separate method)
        id_errors = self._validate_id_formats(claim)
        errors.extend(id_errors)
        
        return errors
# services/rule_engine.py - REPLACE _validate_medical_rules method
# PRODUCTION: Flag ALL medical errors

    def _validate_medical_rules(self, claim: ClaimRecord) -> List[str]:
        """Validate medical rules for a claim - STRICT PRODUCTION VERSION"""
        errors = []
        rules = self.medical_rules
        
        # 1. Check encounter type constraints (CRITICAL)
        if claim.service_code in rules.inpatient_only_services:
            if claim.encounter_type != "INPATIENT":
                errors.append(
                    f"Medical Error: Service {claim.service_code} is INPATIENT-only but encounter type is {claim.encounter_type}"
                )
        
        if claim.service_code in rules.outpatient_only_services:
            if claim.encounter_type != "OUTPATIENT":
                errors.append(
                    f"Medical Error: Service {claim.service_code} is OUTPATIENT-only but encounter type is {claim.encounter_type}"
                )
        
        # 2. Check facility-service constraints
        facility_type = rules.facility_registry.get(claim.facility_id.upper())
        if not facility_type:
            # Try case-insensitive lookup
            facility_type = next(
                (v for k, v in rules.facility_registry.items() if k.upper() == claim.facility_id.upper()),
                None
            )
        
        if facility_type:
            allowed_services = rules.facility_service_mapping.get(facility_type, [])
            if claim.service_code not in allowed_services:
                errors.append(
                    f"Medical Error: Service {claim.service_code} is not authorized at {facility_type} facilities (Facility ID: {claim.facility_id})"
                )
        else:
            errors.append(
                f"Medical Error: Facility ID '{claim.facility_id}' is not registered in the system"
            )
        
        # 3. Check diagnosis-service requirements (STRICT ENFORCEMENT)
        # If a diagnosis is present that REQUIRES a specific service, that service MUST be provided
        for diagnosis in claim.diagnosis_codes:
            if diagnosis in rules.diagnosis_service_requirements:
                required_services = rules.diagnosis_service_requirements[diagnosis]
                if claim.service_code not in required_services:
                    service_list = ", ".join(required_services)
                    errors.append(
                        f"Medical Error: Diagnosis {diagnosis} requires service {service_list}, but service {claim.service_code} was provided"
                    )
        
        # 4. Check mutually exclusive diagnoses (CRITICAL)
        for diag1, diag2 in rules.mutually_exclusive_diagnoses:
            if diag1 in claim.diagnosis_codes and diag2 in claim.diagnosis_codes:
                errors.append(
                    f"Medical Error: Diagnoses {diag1} and {diag2} are mutually exclusive and cannot both be present on the same claim"
                )
        
        return errors
    # services/rule_engine.py - REPLACE _validate_id_formats method
# PRODUCTION VERSION: Only validate format, not segment matching

    # services/rule_engine.py - REPLACE _validate_id_formats method
# PRODUCTION: STRICT validation - flag ALL errors

    def _validate_id_formats(self, claim: ClaimRecord) -> List[str]:
        """
        Validate ID formatting rules - STRICT PRODUCTION VERSION
        Flags ALL ID-related errors according to technical rules
        """
        errors = []
        rules = self.technical_rules.id_format_rules
        
        # 1. Check unique_id format (XXXX-XXXX-XXXX pattern with uppercase alphanumeric)
        if not re.match(rules["pattern"], claim.unique_id):
            errors.append(
                f"Technical Error: unique_id '{claim.unique_id}' must follow format XXXX-XXXX-XXXX with uppercase alphanumeric characters only"
            )
        
        # 2. Check for placeholder values (invalid)
        if claim.unique_id.upper() in ["XXXX-YYYY-ZZZZ", "XXXX-XXXX-XXXX"]:
            errors.append(
                f"Technical Error: unique_id cannot be a placeholder value '{claim.unique_id}'"
            )
        
        # 3. Validate segment structure if format is correct
        if re.match(rules["pattern"], claim.unique_id):
            segments = claim.unique_id.split('-')
            
            # Normalize source IDs to uppercase for comparison
            national_upper = claim.national_id.upper()
            member_upper = claim.member_id.upper()
            facility_upper = claim.facility_id.upper()
            
            # Extract expected segments based on rules:
            # "first4(National ID) – middle4(Member ID) – last4(Facility ID)"
            
            # First segment: first 4 chars of national_id
            if len(national_upper) >= 4:
                expected_first = national_upper[:4]
                if segments[0] != expected_first:
                    errors.append(
                        f"Technical Error: unique_id first segment '{segments[0]}' must be first 4 characters of national_id (expected '{expected_first}')"
                    )
            else:
                errors.append(
                    f"Technical Error: national_id '{claim.national_id}' must be at least 4 characters long"
                )
            
            # Middle segment: middle 4 chars of member_id (chars at positions 2-5 for 8-char ID)
            if len(member_upper) >= 8:
                # For 8-character member_id, middle 4 = positions 2-5 (0-indexed: [2:6])
                expected_middle = member_upper[2:6]
                if segments[1] != expected_middle:
                    errors.append(
                        f"Technical Error: unique_id middle segment '{segments[1]}' must be middle 4 characters of member_id (expected '{expected_middle}', positions 3-6)"
                    )
            elif len(member_upper) >= 4:
                # If member_id < 8 chars, check if segment exists in member_id
                if segments[1] not in member_upper:
                    errors.append(
                        f"Technical Error: unique_id middle segment '{segments[1]}' not found in member_id '{claim.member_id}'"
                    )
            else:
                errors.append(
                    f"Technical Error: member_id '{claim.member_id}' must be at least 4 characters long"
                )
            
            # Last segment: last 4 chars of facility_id
            if len(facility_upper) >= 4:
                expected_last = facility_upper[-4:]
                if segments[2] != expected_last:
                    errors.append(
                        f"Technical Error: unique_id last segment '{segments[2]}' must be last 4 characters of facility_id (expected '{expected_last}')"
                    )
            else:
                errors.append(
                    f"Technical Error: facility_id '{claim.facility_id}' must be at least 4 characters long"
                )
        
        # 4. Validate individual ID formats (must be uppercase alphanumeric)
        for id_field, id_value in [
            ("national_id", claim.national_id),
            ("member_id", claim.member_id),
            ("facility_id", claim.facility_id)
        ]:
            # Check if contains only alphanumeric characters
            if not id_value.replace('-', '').isalnum():
                errors.append(
                    f"Technical Error: {id_field} '{id_value}' contains invalid characters (must be alphanumeric only)"
                )
            
            # Check if all uppercase (as per rules: "All IDs must be UPPERCASE")
            if id_value != id_value.upper():
                errors.append(
                    f"Technical Error: {id_field} '{id_value}' must be UPPERCASE alphanumeric (found lowercase characters)"
                )
        
        return errors

    def _generate_recommended_action(
        self, 
        technical_errors: List[str], 
        medical_errors: List[str], 
        claim: ClaimRecord
    ) -> str:
        """Generate actionable recommendations based on errors found"""
        actions = []
        
        # Technical error actions
        for error in technical_errors:
            if "prior approval" in error.lower():
                actions.append("Obtain prior approval before processing")
            elif "unique_id" in error.lower():
                actions.append("Correct ID formatting to uppercase alphanumeric")
            elif "threshold" in error.lower():
                actions.append("Request prior approval for high-value claim")
        
        # Medical error actions
        for error in medical_errors:
            if "encounter" in error.lower():
                actions.append("Verify encounter type matches service requirements")
            elif "facility" in error.lower():
                actions.append("Transfer to appropriate facility or update facility code")
            elif "diagnosis" in error.lower() and "requires" in error.lower():
                actions.append("Update service code to match diagnosis requirements")
            elif "mutually exclusive" in error.lower():
                actions.append("Review and correct diagnosis codes")
        
        # Default action if no specific recommendations
        if not actions:
            actions.append("Review claim details and correct identified issues")
        
        # Remove duplicates and join
        unique_actions = list(set(actions))
        return "; ".join(unique_actions)
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """Get summary of loaded rules for debugging"""
        summary = {
            "technical_rules_loaded": self.technical_rules is not None,
            "medical_rules_loaded": self.medical_rules is not None
        }
        
        if self.technical_rules:
            summary["technical_rules"] = {
                "services_requiring_approval": len(self.technical_rules.services_requiring_approval),
                "diagnosis_requiring_approval": len(self.technical_rules.diagnosis_requiring_approval),
                "paid_amount_threshold": self.technical_rules.paid_amount_threshold
            }
        
        if self.medical_rules:
            summary["medical_rules"] = {
                "inpatient_only_services": len(self.medical_rules.inpatient_only_services),
                "outpatient_only_services": len(self.medical_rules.outpatient_only_services),
                "facilities_registered": len(self.medical_rules.facility_registry),
                "diagnosis_service_requirements": len(self.medical_rules.diagnosis_service_requirements),
                "mutually_exclusive_pairs": len(self.medical_rules.mutually_exclusive_diagnoses)
            }
        
        return summary