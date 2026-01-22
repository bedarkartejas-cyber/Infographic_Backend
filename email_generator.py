from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_marketing_email(marketing_brief: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional copywriter."},
            {"role": "user", "content": f"""
Write a marketing email using the brief below.
Include keys: "subject", "body".
Brief:
{marketing_brief}

Return JSON object only.
"""}
        ],
        temperature=0.6,
        response_format={ "type": "json_object" }
    )
    return response.choices[0].message.content