from typing import Dict

CANONICAL_LABELS = {
    "Album": "CreativeWork",
    "Song": "CreativeWork",
    "Movie": "CreativeWork",
    "TVShow": "CreativeWork",
    "TV Show": "CreativeWork",
    "Television Series": "CreativeWork",
    "School": "EducationalInstitution",
    "University": "EducationalInstitution",
    "College": "EducationalInstitution",
    "Academy": "EducationalInstitution",
    "Educational Institution": "EducationalInstitution"
}

class OntologyNormalizer:
    """
    Normalizes raw extracted entity labels to canonical ontology labels.
    """
    def __init__(self):
        self.mappings = CANONICAL_LABELS

    def normalize(self, label: str) -> str:
        if not label:
            return "Other"
        
        title_case = label.strip().title()
        
        # 1. Check exact mapping
        if title_case in self.mappings:
            return self.mappings[title_case]
            
        # 2. Check compact mapping (no spaces)
        compact = title_case.replace(" ", "")
        if compact in self.mappings:
            return self.mappings[compact]
            
        # 3. Check if already standard ontology label
        from graphmem.agents.extractor import ONTOLOGY_LABELS
        if title_case in ONTOLOGY_LABELS:
            return title_case
        if compact in ONTOLOGY_LABELS:
            return compact
            
        return "Other"
