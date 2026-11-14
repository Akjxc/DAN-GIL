import { apiUrl } from './apiClient.js';

export async function requestPlaces(signal) {
  const response = await fetch(apiUrl('/api/places'), { signal });
  if (!response.ok) throw new Error('실내 장소 목록을 불러오지 못했습니다.');
  return response.json();
}

export async function requestRoute(start, end, avoidStairs, signal, mode = 'fast') {
  const response = await fetch(apiUrl('/api/routes'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      start_node_id: start,
      end_node_id: end,
      exclude_conditions: avoidStairs ? ['stair'] : [],
      allow_exceptions: avoidStairs || mode === 'indoor',
      exclude_kinds: mode === 'indoor' ? ['outdoorPath'] : [],
    }),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(typeof result?.detail === 'string' ? result.detail : '경로 서버에 연결하지 못했습니다. 백엔드 실행 상태를 확인해 주세요.');
  }
  if (result?.status === 'no_route') return null;
  if (result?.status !== 'ok') throw new Error('올바른 경로를 받지 못했습니다.');
  return result;
}
