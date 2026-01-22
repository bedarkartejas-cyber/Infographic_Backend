import json
import re

def parse_llm_json(text: str):
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    cleaned = cleaned.strip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Fallback: attempt to find the first '{' and last '}'
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start != -1 and end != 0:
            try:
                return json.loads(cleaned[start:end])
            except:
                pass
        raise ValueError(f"LLM did not return valid JSON. Error: {e}")
