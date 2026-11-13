import { modes } from "../algorithms/routeCalculator";
export default function RouteResult({ route, mode, names }) {
  if (!route)
    return (
      <div className="empty">
        ⌁<p>장소를 선택하고 경로를 검색해 보세요.</p>
      </div>
    );
  return (
    <div className="result" style={{ "--c": modes[mode].color }}>
      <header>
        <span>추천 경로</span>
        <b>{modes[mode].label}</b>
      </header>
      <section>
        <div>
          <strong>약 {route.time}분</strong>
          <small>시연용 예상 시간</small>
        </div>
        <div>
          <strong>{route.walking}m</strong>
          <small>Mock 보행거리</small>
        </div>
      </section>
      <p>{route.path.map((id) => names[id] || id).join("  ›  ")}</p>
      <small>실측값이 아닌 기능 시연용 계산 결과입니다.</small>
    </div>
  );
}
