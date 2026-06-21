import logging
from typing import Optional, Tuple
from graphmem.agents.extractor import ONTOLOGY_LABELS, ONTOLOGY_RELATIONS

logger = logging.getLogger(__name__)

class RelationValidator:
    """
    Three-Layer Relation Validation System for GraphMem:
    1. Structural Validation (reject obvious garbage like self-loops, empty values)
    2. Ontology Validation (checks if source/target labels and relations are in standard sets)
    3. Evidence Validation & Confidence Penalty (checks for blunders like DIED_IN without death keywords,
       applies confidence multipliers for missing/weak textual evidence).
    """
    
    @staticmethod
    def validate(
        source_name: str,
        source_label: str,
        target_name: str,
        target_label: str,
        relation: str,
        evidence_text: Optional[str] = None,
        fact: Optional[str] = None
    ) -> Tuple[bool, float]:
        """
        Validates a relation and calculates a confidence multiplier.
        
        Returns:
            (is_valid: bool, confidence_multiplier: float)
        """
        # --- LAYER 1: STRUCTURAL VALIDATION ---
        # 1. Reject empty values
        if not relation or not relation.strip():
            logger.warning("Structural Validation: Rejected relation with empty relation type.")
            return False, 0.0
        if not source_name or not target_name:
            logger.warning("Structural Validation: Rejected relation with missing entity names.")
            return False, 0.0
            
        # 2. Reject self-loops (obvious garbage)
        if source_name.strip().lower() == target_name.strip().lower():
            logger.warning(f"Structural Validation: Rejected self-loop relation for entity '{source_name}'.")
            return False, 0.0
            
        # --- LAYER 2: ONTOLOGY VALIDATION ---
        # 1. Validate source and target labels are in standard ontology labels
        if source_label not in ONTOLOGY_LABELS or target_label not in ONTOLOGY_LABELS:
            logger.warning(
                f"Ontology Validation: Rejected relation. Source label '{source_label}' or "
                f"target label '{target_label}' is not in standard ontology labels."
            )
            return False, 0.0
            
        # 2. Validate relation type is standard ontology
        if relation not in ONTOLOGY_RELATIONS:
            logger.warning(f"Ontology Validation: Rejected non-standard relation type '{relation}'.")
            return False, 0.0
            
        # --- LAYER 3: EVIDENCE VALIDATION & CONFIDENCE PENALTY ---
        confidence_multiplier = 1.0
        
        # 1. Semantic Blunder Check: DIED_IN requires explicit death keywords in text
        if relation == "DIED_IN":
            if source_label != "Person" or target_label != "Location":
                logger.warning(f"Evidence Validation: Rejected DIED_IN relation between '{source_label}' and '{target_label}'.")
                return False, 0.0
                
            evidence = (evidence_text or "").lower()
            fact_str = (fact or "").lower()
            death_keywords = [
                "died", "death", "killed", "fatal", "murdered", "assassinated", 
                "deceased", "passed away", "buried", "gravestone", "cemetery"
            ]
            has_death_evidence = any(kw in evidence or kw in fact_str for kw in death_keywords)
            if not has_death_evidence:
                logger.warning(
                    f"Evidence Validation: Rejected DIED_IN relation for '{source_name}' "
                    "due to lack of explicit death keywords in evidence text."
                )
                return False, 0.0
                
        # 2. Confidence Penalty: Missing evidence text (50% penalty)
        if not evidence_text or not evidence_text.strip():
            logger.info(
                f"Evidence Validation: 50% confidence penalty applied to '{source_name} -{relation}-> {target_name}' "
                "due to missing evidence text."
            )
            confidence_multiplier *= 0.5
        else:
            # 3. Confidence Penalty: Weak Entity Co-occurrence check (20% penalty)
            # Check if source or target words are present in the evidence text
            evidence_lower = evidence_text.lower()
            
            # Split names to find key words (skip short stop-like words)
            src_words = [w.lower() for w in source_name.split() if len(w) > 2]
            tgt_words = [w.lower() for w in target_name.split() if len(w) > 2]
            
            if not src_words:
                src_words = [source_name.lower()]
            if not tgt_words:
                tgt_words = [target_name.lower()]
                
            source_mentioned = any(word in evidence_lower for word in src_words)
            target_mentioned = any(word in evidence_lower for word in tgt_words)
            
            if not source_mentioned or not target_mentioned:
                logger.info(
                    f"Evidence Validation: 20% confidence penalty applied to '{source_name} -{relation}-> {target_name}' "
                    "due to weak entity co-occurrence in evidence."
                )
                confidence_multiplier *= 0.8
                
        return True, confidence_multiplier
