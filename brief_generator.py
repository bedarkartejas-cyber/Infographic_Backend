from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_marketing_brief(source_context: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system", 
                "content": "You are a senior marketing strategist who also thinks in terms of product structure, system components, and visual metaphors. Write briefs that are useful for both copywriting and visual design."
            },
            {
                "role": "user", 
                "content": f"""
From the sources below, generate a marketing brief.
Return a JSON OBJECT with EXACTLY these keys:
- product_or_service
- target_audience
- value_proposition
- key_benefits (array of strings)
- tone_of_voice
- call_to_action

Sources:
{source_context}
"""}
        ],
        temperature=0.3,
        response_format={ "type": "json_object" }
    )
    return response.choices[0].message.content