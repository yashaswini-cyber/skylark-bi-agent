import json

from google import genai
from google.genai import types

from config import GEMINI_API_KEY
from models import AnalyticsIntent, AnalyticsRequest


PLANNER_MODEL = "gemini-3.6-flash"


class QueryPlanner:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = PLANNER_MODEL) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def plan(self, question: str) -> AnalyticsRequest:
        prompt = (
            "Map the user's BI question to one supported analytics intent. "
            "Supported intents: open_pipeline, won_business, sector_pipeline, "
            "deal_stage_analysis, work_order_status, billing_summary, "
            "sector_operations, cross_board_sector_analysis, data_quality. "
            "Extract sector, deal_stage, or status only when explicitly present. "
            "If a required parameter is missing or the question is ambiguous, use intent clarification "
            "and ask one short clarification_question. Do not calculate metrics.\n\n"
            f"Question: {question}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                response_mime_type="application/json",
                response_json_schema=AnalyticsRequest.model_json_schema(),
            ),
        )

        if response.parsed:
            return AnalyticsRequest.model_validate(response.parsed)

        return AnalyticsRequest.model_validate(json.loads(response.text))


def plan_query(question: str) -> AnalyticsRequest:
    return QueryPlanner().plan(question)
