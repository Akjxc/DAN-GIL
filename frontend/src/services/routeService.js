export async function requestRoute(start, end, avoidStairs, signal) {
  const response = await fetch('/api/routes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      start_node_id: start,
      end_node_id: end,
      exclude_conditions: avoidStairs ? ['stair'] : [],
      exclude_kinds: [],
    }),
  });
  if (!response.ok) throw new Error('경로 서버에 연결하지 못했습니다. 백엔드 실행 상태를 확인해 주세요.');
  const result = await response.json();
  if (result.status === 'no_route') return null;
  if (result.status !== 'ok') throw new Error('올바른 경로를 받지 못했습니다.');
  return { ...result, path: result.nodes.map(n => n.id) };
}
