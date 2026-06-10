import asyncio
import json
from graphmem.agents.extractor import Extractor

async def test_extractor():
    extractor = Extractor()
    
    test_text = (
        "Microsoft, led by CEO Satya Nadella, recently announced a significant investment in OpenAI. "
        "The partnership aims to accelerate breakthroughs in AI, specifically targeting research "
        "at OpenAI's labs in San Francisco."
    )
    
    print("Extracting from text...")
    result = await extractor.extract(test_text)
    
    print("\nExtraction Result:")
    print(json.dumps(result, indent=2))
    
    # Simple validation
    entities = result.get("entities", [])
    relations = result.get("relations", [])
    
    if len(entities) > 0:
        print(f"\n✓ Extracted {len(entities)} entities.")
    else:
        print("\n× No entities extracted.")
        
    if len(relations) > 0:
        print(f"✓ Extracted {len(relations)} relations.")
    else:
        print("× No relations extracted.")

if __name__ == "__main__":
    asyncio.run(test_extractor())
