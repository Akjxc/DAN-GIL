export async function sendChatMessage(message, history = []) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({ message, history: history.slice(-20) }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail;
      throw new Error(typeof detail === 'string' ? detail : detail?.message || '채팅 요청을 처리하지 못했어요.');
    }
    if (typeof data.message !== 'string') throw new Error('응답 형식이 올바르지 않습니다.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('답변 대기 시간이 길어졌어요. 다시 질문해 주세요.');
    if (error instanceof TypeError) throw new Error('채팅 서버에 연결하지 못했어요. 백엔드 실행 상태를 확인해 주세요.');
    throw error;
  } finally { clearTimeout(timer); }
}
