import { apiUrl } from './apiClient.js';

export async function sendChatMessage(message, messages = []) {
  const history = messages
    .filter(({ local }) => !local)
    .slice(-20)
    .map(({ role, text }) => ({
      role: role === "bot" ? "assistant" : role,
      content: Array.from(text).slice(0, 4000).join(""),
    }));

  let response;
  try {
    response = await fetch(apiUrl('/api/chat'), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
  } catch {
    throw new Error("채팅 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.");
  }

  const answer = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 429) {
      throw new Error(
        answer?.detail?.message ||
          "채팅 요청 한도에 도달했어요. 잠시 후 다시 시도해 주세요. 지도에서 ‘경로 찾기’는 계속 이용할 수 있어요.",
      );
    }
    throw new Error(
      answer?.detail?.message ??
        (response.status === 422
          ? "메시지 내용을 확인하고 다시 보내 주세요."
          : "채팅 서버에서 답변을 받지 못했어요. 잠시 후 다시 시도해 주세요."),
    );
  }
  if (typeof answer?.message !== "string" || !answer.message.trim()) {
    throw new Error("채팅 서버에서 올바른 답변을 받지 못했어요.");
  }
  return answer;
}
