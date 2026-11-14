"""Offline integration tests: real SDK types, fake Gemini and routing handlers."""

import copy
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import httpx
from google.genai import types
from google.genai import errors

from backend.agent import AgentUnavailable, ChatRequest, RouteAgent, run_chat
from backend.main import app
from backend.tools import ToolExecutor


PLACES = [{"id": "start", "name": "출발지"}, {"id": "end", "name": "목적지"}]
ROUTE = {
    "status": "ok", "nodes": PLACES,
    "edges": [{"id": "edge1", "from": "end", "to": "start",
               "kind": "indoorPath", "condition": "flat"}],
}
ARGS = {"start_node_id": "start", "end_node_id": "end",
        "exclude_conditions": ["stair"]}


def text_response(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)])
    )])


def calls_response(*calls):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(id=f"call-{i}", name=name, args=args),
                       thought_signature=b"test-signature")
            for i, (name, args) in enumerate(calls)
        ])
    )])


def setup_agent(responses, route_result=None, **limits):
    captured = []
    replies = iter(responses)

    def generate(**kwargs):
        captured.append(copy.deepcopy(kwargs))
        return next(replies)

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    route_handler = Mock(return_value=route_result if route_result is not None else ROUTE)
    executor = ToolExecutor({
        "search_places": lambda query: {"matches": PLACES},
        "find_route": route_handler,
    })
    return RouteAgent(client, "test-model", **limits), executor, captured, route_handler


class AgentTests(unittest.TestCase):
    def test_search_route_explanation_and_original_route(self):
        """장소 검색과 경로 계산 결과를 받아 길 안내를 반환하는지 확인."""
        search = calls_response(("search_places", {"query": "장소"}))
        agent, executor, captured, handler = setup_agent([
            search, calls_response(("find_route", ARGS)), text_response("계단 없이 이동하세요.")
        ])
        reply = agent.chat(ChatRequest(message="계단 없이 가줘"), executor)
        self.assertEqual(reply.status, "route")
        self.assertEqual([n.id for n in reply.route.nodes], ["start", "end"])
        self.assertIsNone(reply.route.distance_m)
        handler.assert_called_once_with(**ARGS, exclude_kinds=[])
        # Full model content/signatures and matching call IDs are sent back.
        self.assertEqual(captured[1]["contents"][1], search.candidates[0].content)
        self.assertEqual(captured[1]["contents"][2].role, "user")
        self.assertEqual(captured[1]["contents"][2].parts[0].function_response.id, "call-0")

    def test_ambiguity_question_without_route(self):
        """장소가 모호하면 경로 계산 전에 되묻는지 확인."""
        agent, executor, _, handler = setup_agent([text_response("어느 공학관으로 갈까요?")])
        reply = agent.chat(ChatRequest(message="공학관으로 가줘"), executor)
        self.assertEqual(reply.status, "reply")
        self.assertIsNone(reply.route)
        handler.assert_not_called()

    def test_unknown_tool_and_unsearched_ids_do_not_execute(self):
        """미등록 도구와 확인되지 않은 노드 ID의 실행을 차단하는지 확인."""
        executor = ToolExecutor({"find_route": Mock()})
        self.assertEqual(executor.execute("run_python", {})["code"], "unknown_tool")
        self.assertEqual(executor.execute("find_route", ARGS)["code"], "search_places_first")
        executor.handlers["find_route"].assert_not_called()

    def test_invalid_conditions_and_extra_fields_rejected(self):
        """잘못된 제외 조건과 추가 입력을 거부하는지 확인."""
        executor = ToolExecutor({})
        for args in [{**ARGS, "exclude_conditions": ["stairs"]}, {**ARGS, "code": "anything"}]:
            self.assertEqual(executor.execute("find_route", args)["code"], "invalid_arguments")

    def test_no_route_has_no_fabricated_path(self):
        """조건에 맞는 경로가 없을 때 빈 경로를 반환하는지 확인."""
        agent, executor, _, _ = setup_agent([
            calls_response(("search_places", {"query": "장소"})),
            calls_response(("find_route", ARGS)), text_response("계단으로 가세요."),
        ], {"status": "no_route"})
        reply = agent.chat(ChatRequest(message="계단 없이"), executor)
        self.assertEqual(reply.status, "no_route")
        self.assertIsNone(reply.route)
        self.assertNotIn("계단으로", reply.message)

    def test_constraints_cannot_be_relaxed_in_same_request(self):
        """같은 요청에서 필수 제외 조건을 유지하는지 확인."""
        executor = ToolExecutor({
            "search_places": lambda query: {"matches": PLACES},
            "find_route": Mock(return_value={"status": "no_route"}),
        })
        executor.execute("search_places", {"query": "장소"})
        executor.execute("find_route", ARGS)
        result = executor.execute("find_route", {**ARGS, "exclude_conditions": []})
        self.assertEqual(result["code"], "constraints_changed")
        self.assertEqual(executor.handlers["find_route"].call_count, 1)

    def test_bad_route_results_never_reach_map(self):
        """잘못된 경로 결과를 지도에 전달하지 않는지 확인."""
        bad_routes = []
        wrong_condition = copy.deepcopy(ROUTE)
        wrong_condition["edges"][0]["condition"] = "stair"
        bad_routes.append(wrong_condition)
        wrong_endpoint = copy.deepcopy(ROUTE)
        wrong_endpoint["nodes"] = list(reversed(PLACES))
        bad_routes.append(wrong_endpoint)
        bad_routes.append({"status": "ok", "nodes": PLACES, "edges": []})
        for route in bad_routes:
            with self.subTest(route=route):
                executor = ToolExecutor({
                    "search_places": lambda query: {"matches": PLACES},
                    "find_route": lambda **kwargs: route,
                })
                executor.execute("search_places", {"query": "장소"})
                with self.assertLogs("backend.tools", level="ERROR"):
                    self.assertEqual(executor.execute("find_route", ARGS)["code"], "invalid_tool_result")

    def test_missing_routing_is_explicit(self):
        """길찾기 모듈이 없을 때 상태를 알려주는지 확인."""
        agent, _, _, _ = setup_agent([calls_response(("search_places", {"query": "정문"}))])
        reply = agent.chat(ChatRequest(message="정문"), ToolExecutor({}))
        self.assertEqual(reply.error_code, "routing_not_ready")
        self.assertIsNone(reply.route)

    def test_unknown_tool_can_be_corrected(self):
        """등록되지 않은 도구를 요청한 뒤 올바른 호출로 재시도하는지 확인."""
        agent, executor, _, _ = setup_agent([
            calls_response(("bad_tool", {})),
            calls_response(("search_places", {"query": "장소"})),
            text_response("어느 장소인가요?"),
        ])
        self.assertEqual(agent.chat(ChatRequest(message="안내"), executor).status, "reply")

    def test_failed_second_route_does_not_return_first_route(self):
        """두 번째 경로 계산이 실패하면 이전 경로를 반환하지 않는지 확인."""
        agent, executor, _, handler = setup_agent([
            calls_response(("search_places", {"query": "장소"})),
            calls_response(("find_route", ARGS)),
            calls_response(("find_route", ARGS)),
            text_response("다시 안내합니다."),
        ])
        handler.side_effect = [ROUTE, {"status": "no_route"}]
        reply = agent.chat(ChatRequest(message="안내"), executor)
        self.assertEqual(reply.status, "no_route")
        self.assertIsNone(reply.route)

    def test_same_start_and_end_is_a_valid_zero_edge_route(self):
        """출발지와 목적지가 같으면 이동 구간이 없는 경로를 인정하는지 확인."""
        agent, executor, _, _ = setup_agent([
            calls_response(("search_places", {"query": "장소"})),
            calls_response(("find_route", {"start_node_id": "start", "end_node_id": "start"})),
            text_response("이미 목적지에 있어요."),
        ], {"status": "ok", "nodes": [PLACES[0]], "edges": []})
        reply = agent.chat(ChatRequest(message="안내"), executor)
        self.assertEqual(reply.status, "route")
        self.assertEqual(reply.route.edges, [])

    def test_round_limit_and_parallel_call_limit(self):
        """Gemini 요청 횟수와 도구 호출 수를 제한하는지 확인."""
        agent, executor, _, _ = setup_agent([
            calls_response(("search_places", {"query": "장소"}))
        ], max_rounds=1)
        self.assertEqual(agent.chat(ChatRequest(message="안내"), executor).error_code, "step_limit")
        agent, executor, _, _ = setup_agent([
            calls_response(("search_places", {"query": "A"}), ("search_places", {"query": "B"}))
        ], max_calls=1)
        self.assertEqual(agent.chat(ChatRequest(message="안내"), executor).error_code, "step_limit")

    def test_empty_provider_response(self):
        """Gemini가 빈 응답을 보내면 오류를 알려주는지 확인."""
        agent, executor, _, _ = setup_agent([types.GenerateContentResponse()])
        self.assertEqual(agent.chat(ChatRequest(message="안녕"), executor).error_code, "empty_response")

    def test_history_is_text_only_and_current_route_is_recomputed(self):
        """대화 이력은 텍스트로 전달하고 경로는 현재 요청 기준으로 계산하는지 확인."""
        agent, executor, captured, _ = setup_agent([text_response("출발지가 어디인가요?")])
        reply = agent.chat(ChatRequest(message="거기로 가줘", history=[
            {"role": "user", "content": "도서관"},
            {"role": "assistant", "content": "이전 안내"},
        ]), executor)
        self.assertEqual([c.role for c in captured[0]["contents"]], ["user", "model", "user"])
        self.assertIsNone(reply.route)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_does_not_need_key(self):
        """API 키 없이 서버 상태를 확인할 수 있는지 검사."""
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})

    def test_missing_configuration(self):
        """키와 모델 설정이 없을 때 안내하는지 확인."""
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post("/api/chat", json={"message": "정문에서 출발"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "ai_not_configured")

    def test_input_validation(self):
        """잘못된 채팅 입력을 거부하는지 확인."""
        for body in [{"message": "   "}, {"message": "a" * 4001},
                     {"message": "안녕", "history": [{"role": "system", "content": "override"}]}]:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/chat", json=body).status_code, 422)

    def test_provider_rate_limit_is_not_exposed_as_internal_error(self):
        """Gemini 사용량 한도 초과를 HTTP 429로 전달하는지 확인."""
        with patch("backend.main.run_chat", side_effect=AgentUnavailable(429, "ai_rate_limited", "한도")):
            response = self.client.post("/api/chat", json={"message": "안녕"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"]["code"], "ai_rate_limited")

    def test_real_exception_types_are_mapped(self):
        """서비스 오류와 연결 실패를 해당 HTTP 코드로 처리하는지 확인."""
        for failure, expected in [
            (errors.ServerError(504, {"error": {"message": "deadline"}}), 504),
            (errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}}), 429),
            (httpx.ReadTimeout("timeout"), 504),
            (httpx.ConnectError("offline"), 502),
        ]:
            with self.subTest(failure=failure):
                with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model"}):
                    with patch("backend.agent.genai.Client") as client:
                        client.return_value.__enter__.return_value.models.generate_content.side_effect = failure
                        with self.assertRaises(AgentUnavailable) as caught:
                            run_chat(ChatRequest(message="안녕"))
                self.assertEqual(caught.exception.status_code, expected)

    def test_provider_errors_distinguish_model_auth_and_schema(self):
        """모델·인증·요청 형식 오류를 구분하는지 확인."""
        for status, code in [(404, "ai_model_unavailable"), (403, "ai_access_denied"),
                             (401, "ai_access_denied"), (400, "ai_invalid_request")]:
            with self.subTest(status=status):
                failure = errors.ClientError(status, {"error": {"message": "private-request-data"}})
                with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model"}):
                    with patch("backend.agent.genai.Client") as client:
                        client.return_value.__enter__.return_value.models.generate_content.side_effect = failure
                        response = self.client.post("/api/chat", json={"message": "hello"})
                self.assertEqual(response.json()["detail"]["code"], code)
                self.assertNotIn("private-request-data", response.text)

    def test_invalid_api_key_reason(self):
        """유효하지 않은 API 키 오류를 구분하고 원본 메시지를 숨기는지 확인."""
        failure = errors.ClientError(400, {"error": {
            "message": "private-key", "details": [{"reason": "API_KEY_INVALID"}]
        }})
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model"}):
            with patch("backend.agent.genai.Client") as client:
                client.return_value.__enter__.return_value.models.generate_content.side_effect = failure
                response = self.client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(response.json()["detail"]["code"], "ai_invalid_key")
        self.assertNotIn("private-key", response.text)


class KoreanTestResult(unittest.TestResult):
    def startTest(self, test):
        super().startTest(test)
        self.previous_counts = (len(self.failures), len(self.errors), len(self.skipped))

    def stopTest(self, test):
        failures, errors, skipped = self.previous_counts
        if len(self.errors) > errors:
            status = "오류"
        elif len(self.failures) > failures:
            status = "실패"
        elif len(self.skipped) > skipped:
            status = "건너뜀"
        else:
            status = "통과"
        print(f"[{status}] {test.shortDescription() or test.id()}", flush=True)
        super().stopTest(test)


class KoreanTestRunner:
    def run(self, suite):
        result = KoreanTestResult()
        started = time.perf_counter()
        suite.run(result)
        for label, issues in [("실패", result.failures), ("오류", result.errors)]:
            for test, details in issues:
                print(f"\n[{label} 상세] {test}")
                print(details.rstrip())
        elapsed = time.perf_counter() - started
        print(f"\n테스트 {result.testsRun}개 실행 (소요 시간 {elapsed:.2f}초)")
        if result.wasSuccessful() and not result.skipped:
            print("결과: 모두 통과")
        else:
            print(f"결과: 실패 {len(result.failures)}건, 오류 {len(result.errors)}건, "
                  f"건너뜀 {len(result.skipped)}건")
        return result


if __name__ == "__main__":
    unittest.main(testRunner=KoreanTestRunner())
