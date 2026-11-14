export async function requestPlaces(signal) {
  const response = await fetch('/api/places?endpoints_only=true', { signal });
  if (!response.ok) throw new Error('실내 장소 목록을 불러오지 못했습니다.');
  const nodes = await response.json();
  const landmarks = {
    mainGate: '단국대 정문',
    bearStatue: '곰상(평화의광장)',
    parkingJc: '주차빌딩 앞',
    labJc: '종합실험동 앞',
    hyeDangYardJc: '노천마당 앞',
    dentalJc: '치과대학 방면',
  };
  return nodes
    .filter(node => node.kind === 'entrance' || Object.hasOwn(landmarks, node.id))
    .map(node => ({ ...node, name: landmarks[node.id] || node.name }));
}

export async function requestRoute(start, end, avoidStairs, signal, mode = 'shortest') {
  const response = await fetch('/api/routes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      start_node_id: start,
      end_node_id: end,
      metric: mode === 'shortest' ? 'distance' : mode === 'indoor' ? 'indoor_priority' : 'cost',
      exclude_conditions: avoidStairs ? ['stair'] : [],
      allow_exceptions: avoidStairs,
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
