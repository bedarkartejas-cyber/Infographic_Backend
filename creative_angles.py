from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_creative_angles(marketing_brief: str, count: int ) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system", 
                "content": "You are a creative director."
            },
            {
                "role": "user", 
                "content": f"""
From the brief below, generate exactly {count} distinct creative angles.

Each angle must include:
- angle_name
- intent
- visual_focus (what the image should visually emphasize, e.g. workflow, system, outcome, comparison)

Brief:
{marketing_brief}

Return JSON object with key "angles".

""",
}
        ],
        temperature=0.6,
        response_format={ "type": "json_object" }
    )
    return response.choices[0].message.content

#  f"""
# From the brief below, generate {count} distinct ad creative angles.
# Each must include: "angle_name", "intent".
# Brief:
# {marketing_brief}

# Return JSON object with key "angles" containing the array.
# """