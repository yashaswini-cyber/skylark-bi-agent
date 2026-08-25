from fastapi.testclient import TestClient

import main as api_main
from models import AnalyticsIntent, AnalyticsRequest, BusinessAnswer


class FakeQueryPlanner:
    def plan(self, question: str) -> AnalyticsRequest:
        question_key = question.lower()
        if "sector" in question_key or "pipeline by" in question_key:
            return AnalyticsRequest(intent=AnalyticsIntent.SECTOR_PIPELINE)
        if "billed" in question_key or "receivable" in question_key or "collected" in question_key:
            return AnalyticsRequest(intent=AnalyticsIntent.BILLING_SUMMARY)
        if "execution status" in question_key or "work order" in question_key:
            return AnalyticsRequest(intent=AnalyticsIntent.WORK_ORDER_STATUS)
        return AnalyticsRequest(
            intent=AnalyticsIntent.CLARIFICATION,
            clarification_question="Which business metric should I analyze?",
        )


class FakeAnswerGenerator:
    def generate(self, question, verified_result):
        return BusinessAnswer(answer=f"Verified result for {verified_result.intent.value}.")


api_main.QueryPlanner = FakeQueryPlanner
api_main.AnswerGenerator = FakeAnswerGenerator


def _post_chat(client: TestClient, message: str) -> dict:
    response = client.post("/api/chat", json={"message": message})
    print(f"Question: {message}")
    print(f"Status code: {response.status_code}")
    if response.status_code >= 400:
        print(f"Error response: {response.text}")
    response.raise_for_status()

    payload = response.json()
    print(f"Intent: {payload['intent']}")
    print(f"Answer: {payload['answer']}")
    print(f"Analytics result: {payload['analytics_result']}")
    return payload


def main() -> int:
    client = TestClient(api_main.app)

    health = client.get("/health")
    print(f"Health status code: {health.status_code}")
    health.raise_for_status()

    _post_chat(client, "Show open pipeline by sector.")
    _post_chat(client, "How much has been billed, collected, and receivable?")
    _post_chat(client, "How many work orders are in each execution status?")

    print("API test: success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
