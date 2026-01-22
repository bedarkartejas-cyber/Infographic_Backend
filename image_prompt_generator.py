from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_image_prompts(marketing_brief: str, creative_angles: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior visual designer specializing in professional "
                    "B2B marketing visuals, product infographics, technical diagrams, "
                    "and social media brand graphics. You think in terms of layout, "
                    "visual hierarchy, and information clarity. "
                    "Your outputs look designed, not illustrated."
                )
            },
            {
                "role": "user",
                "content": f"""
You will generate image-generation prompts for marketing visuals.

CRITICAL RULE:
- The final image prompt must be LONG, STRUCTURED, and EXECUTABLE.
- Do NOT write summaries, descriptions, or captions INSIDE the image prompt.
- Write prompts that read like a design specification given to a visual designer.
- If the output could be used as a caption, it is WRONG.

NEW REQUIREMENT:
- In addition to the full image-generation prompt, generate a SHORT, USER-FACING SUMMARY.
- This summary is NOT part of the image prompt.
- It should read like a feature explanation or caption a user would see next to the image.
- It must be concise, plain-language, and explain what the visual shows and why it matters.

INTERNAL PROCESS (do not output these steps):
1. Infer product category and complexity from the marketing brief.
2. For each creative angle, derive a VISUAL BRIEF with:
   - Visual format (choose ONE): infographic, workflow diagram, system architecture, UI feature panel, comparison visual
   - Primary visual metaphor (flow, hub-and-spoke, layered stack, timeline)
   - Information density (low / medium / high)
   - Focal point
3. Convert the visual brief into a FULL DESIGN PROMPT using the REQUIRED FORMAT below.
4. Separately generate a one-sentence USER SUMMARY describing the visual at a feature level.

REQUIRED FINAL PROMPT FORMAT (MUST FOLLOW EXACTLY):

Title:
(one short internal title, not marketing copy)

Visual Type:
(explicitly state the visual format)

Layout & Composition:
(bullet points describing layout zones, hierarchy, spacing, reading order)

Core Visual Elements:
(bullet points describing what is drawn, where, and how elements relate spatially)

Data / UI Representation:
(bullet points describing charts, panels, metrics, flows, arrows, dashboards)

Style & Aesthetic:
(bullet points defining flat vs isometric, realism level, color mood, contrast)

Constraints:
(bullet points listing what must NOT appear)

Purpose:
(one sentence describing what the viewer should understand in 3 seconds)

GLOBAL CONSTRAINTS (apply to all prompts):
- Diagrammatic / schematic, not marketing poster or hero art
- No headline-style text embedded in image
- No cinematic lighting, glow, or concept art
- No realistic people as main subjects (icons or silhouettes only)
- Clean, professional, brand-neutral
- Aspect ratio: 4:5, social media feed optimized

MARKETING BRIEF:
{marketing_brief}

CREATIVE ANGLES:
{creative_angles}

OUTPUT:
Return JSON only:
{{
  "prompts": [
    {{
      "angle_name": "...",
      "summary": "Plain-language explanation of what the image visualizes and the feature or insight it communicates.",
      "prompt": "FULL STRUCTURED PROMPT TEXT"
    }}
  ]
}}

"""
            }
        ],
        temperature=0.5,
        response_format={"type": "json_object"}
    )

    return response.choices[0].message.content
