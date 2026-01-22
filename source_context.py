def build_source_context(ppt_text: str, website_text: str) -> str:
    return f"""
SOURCE: PRESENTATION
{ppt_text}

SOURCE: WEBSITE
{website_text}
""".strip()
