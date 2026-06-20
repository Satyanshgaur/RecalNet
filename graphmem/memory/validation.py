import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Valid ontology triples (source_label, relation, target_label)
ALLOWED_SCHEMAS = {
    ("Person", "ACTED_IN", "CreativeWork"),
    ("Person", "PRODUCED", "CreativeWork"),
    ("Person", "DIRECTED", "CreativeWork"),
    ("Person", "FOUNDED", "Organization"),
    ("Person", "FOUNDED", "EducationalInstitution"),
    ("Person", "CEO_OF", "Organization"),
    ("Person", "CEO_OF", "EducationalInstitution"),
    ("Organization", "LOCATED_IN", "Location"),
    ("EducationalInstitution", "LOCATED_IN", "Location"),
    ("Location", "LOCATED_IN", "Location"),
    ("Person", "WORKS_AT", "Organization"),
    ("Person", "WORKS_AT", "EducationalInstitution"),
    ("Person", "PARTNER_OF", "Person"),
    ("Organization", "PARTNER_OF", "Organization"),
    ("Person", "MEMBER_OF", "Organization"),
    ("Person", "MEMBER_OF", "EducationalInstitution"),
    ("Organization", "SUBSIDIARY_OF", "Organization"),
    ("Person", "DEVELOPED", "Product"),
    ("Person", "DEVELOPED", "CreativeWork"),
    ("Organization", "DEVELOPED", "Product"),
    ("Organization", "DEVELOPED", "CreativeWork"),
    ("Person", "LEADS", "Organization"),
    ("Person", "LEADS", "EducationalInstitution"),
    ("Person", "BORN_IN", "Location"),
    ("Person", "DIED_IN", "Location"),
    ("Person", "CITIZEN_OF", "Location"),
    ("Person", "AWARDED", "Achievement"),
    ("Person", "AWARDED", "CreativeWork"),
    ("Person", "MARRIED_TO", "Person"),
    ("Person", "CHILD_OF", "Person"),
    ("Person", "SIBLING_OF", "Person"),
    ("Person", "ATTENDED", "EducationalInstitution"),
    ("Person", "ATTENDED", "Organization"),
}

class RelationValidator:
    """
    Validates semantic correctness of extracted relations before edge insertion.
    """
    
    @staticmethod
    def validate(
        source_label: str,
        relation: str,
        target_label: str,
        evidence_text: Optional[str] = None,
        fact: Optional[str] = None
    ) -> bool:
        # 1. Fallback for OTHER relation - always allowed
        if relation == "OTHER":
            return True
            
        # 2. Strict Schema Check
        triple = (source_label, relation, target_label)
        if triple not in ALLOWED_SCHEMAS:
            logger.warning(
                f"Relation validation failed: {source_label} --[{relation}]--> {target_label} is not a valid schema triple."
            )
            return False
            
        # 3. Special Case: DIED_IN requires explicit death keywords in evidence/fact
        if relation == "DIED_IN":
            evidence = (evidence_text or "").lower()
            fact_str = (fact or "").lower()
            death_keywords = [
                "died", "death", "killed", "fatal", "murdered", "assassinated", 
                "deceased", "passed away", "buried", "gravestone", "cemetery"
            ]
            has_death_evidence = any(kw in evidence or kw in fact_str for kw in death_keywords)
            if not has_death_evidence:
                logger.warning(
                    f"Relation validation failed: DIED_IN relation between {source_label} and {target_label} lacks explicit death evidence in text."
                )
                return False
                
        return True
