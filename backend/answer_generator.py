import json

from google import genai
from google.genai import types

from config import GEMINI_API_KEY
from models import BusinessAnswer, VerifiedAnalyticsResult


ANSWER_MODEL = "gemini-3.6-flash"


class AnswerGenerator:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = ANSWER_MODEL) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, question: str, verified_result: VerifiedAnalyticsResult) -> BusinessAnswer:
        result_json = verified_result.model_dump_json()
        prompt = (
            "Write a concise founder-level business answer. "
            "Use only the verified analytics result below. "
            "Do not invent, estimate, recalculate, or add numbers. "
            "Do not add currency symbols or units that are not in the verified result. "
            "If the result lacks enough information, say what is missing.\n\n"
            f"Question: {question}\n"
            f"Verified analytics result: {result_json}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                response_mime_type="application/json",
                response_json_schema=BusinessAnswer.model_json_schema(),
            ),
        )

        if response.parsed:
            return BusinessAnswer.model_validate(response.parsed)

        return BusinessAnswer.model_validate(json.loads(response.text))


def generate_answer(question: str, verified_result: VerifiedAnalyticsResult) -> BusinessAnswer:
    return AnswerGenerator().generate(question, verified_result)


def fallback_answer(verified_result: VerifiedAnalyticsResult) -> BusinessAnswer:
    """Build an answer from verified analytics only, without calling Gemini or inventing numbers."""
    payload = json.dumps(verified_result.result, default=str)
    return BusinessAnswer(
        answer=(
            "AI summarization is temporarily unavailable. "
            "Verified analytics result: "
            f"{payload}"
        )
    )
