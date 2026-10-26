from openai import AsyncOpenAI

from app.config import settings


client = AsyncOpenAI(
    base_url=settings.llm_base_url if settings.llm_provider == "ollama" else None,
    api_key="ollama" if settings.llm_provider == "ollama" else settings.openai_api_key,
)


async def generate_text(prompt: str) -> str:
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError("The LLM returned an empty response.")

    return content