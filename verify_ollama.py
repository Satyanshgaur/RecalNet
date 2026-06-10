import asyncio
import json
from graphmem.core.ollama_client import OllamaClient
from graphmem.core.config import settings

async def verify_qwen():
    # Use the model from settings (updated to qwen2.5:7b)
    model = settings.model_name
    print(f"Verifying Ollama with model: {model}...")
    
    client = OllamaClient()
    
    # Prompt specifically designed to get a JSON response
    prompt = "Respond ONLY with a JSON object. The object should have two fields: 'status' (string, value 'ok') and 'message' (string, value 'Hello from Qwen')."
    
    try:
        print("Sending request to Ollama...")
        # We use format="json" if the model supports it, but Qwen usually does well with just the prompt
        # Ollama's /api/generate supports a "format": "json" parameter
        response = await client.generate(prompt, format="json")
        
        raw_text = response.get("response", "").strip()
        print(f"Raw response: {raw_text}")
        
        parsed = json.loads(raw_text)
        print("Successfully parsed JSON:")
        print(json.dumps(parsed, indent=2))
        
        if parsed.get("status") == "ok":
            print("\nVerification SUCCESSFUL!")
        else:
            print("\nVerification FAILED: Unexpected content.")
            
    except Exception as e:
        print(f"\nVerification FAILED with error: {str(e)}")
        print("Tip: Make sure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull qwen`).")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(verify_qwen())
