import { nodes } from "../data/nodes";
import { buildings } from "../data/buildings";
import { modes } from "../algorithms/routeCalculator";
import FacilityMarker from "./FacilityMarker";
import FacilityFilter from "./FacilityFilter";
const N = Object.fromEntries(nodes.map((n) => [n.id, n]));
export default function CampusMap(p) {
  let {
      route,
      mode,
      facilities,
      filter,
      setFilter,
      selectedFacility,
      setSelectedFacility,
      start,
      end,
    } = p,
    points = route?.path
      .map((id) => N[id])
      .map((n) => n.x + "," + n.y)
      .join(" ");
  return (
    <main className="map">
      <header>
        <b>
          <i /> 죽전캠퍼스 시연 지도
        </b>
        <span>실제 위치 아님 · Mock Map</span>
      </header>
      <div className="canvas">
        <svg className="roads" viewBox="0 0 100 100" preserveAspectRatio="none">
          <path d="M69 98L65 84L50 70L40 43L45 32M65 84L50 86M65 84L68 72L55 52M50 70L27 66L29 56L30 47M40 43L55 52L75 47L94 46M75 47L72 36L83 29L89 8M75 47L78 57L87 80" />
          <path className="light" d="M69 95L65 84L68 72L55 52L75 47L89 8" />
        </svg>
        {buildings.map((b) => (
          <div
            className={`building ${b.tone || ""}`}
            key={b.id}
            style={{
              left: b.x + "%",
              top: b.y + "%",
              width: b.w + "%",
              height: b.h + "%",
              "--rotate": (b.rotate || 0) + "deg",
            }}
          >
            <b>{b.name}</b>
            {b.sub && <em>{b.sub}</em>}
            {b.f > 0 && <small>{b.f}F</small>}
          </div>
        ))}
        <svg className="route" viewBox="0 0 100 100" preserveAspectRatio="none">
          {points && (
            <>
              <polyline className="shadow" points={points} />
              <polyline points={points} style={{ stroke: modes[mode].color }} />
            </>
          )}
        </svg>
        {nodes
          .filter((n) => ["portal", "shuttle", "elevator"].includes(n.type))
          .map((n) => (
            <span
              className={"special " + n.type}
              style={{ left: n.x + "%", top: n.y + "%" }}
              title={n.name}
              key={n.id}
            >
              {n.type === "portal" ? "◎" : n.type === "shuttle" ? "▰" : "↕"}
            </span>
          ))}
        {facilities
          .filter((f) => filter === "all" || f.type === filter)
          .map((f) => (
            <FacilityMarker
              facility={f}
              selected={selectedFacility?.id === f.id}
              onClick={setSelectedFacility}
              key={f.id}
            />
          ))}
        {start && (
          <span
            className="pin a"
            style={{ left: N[start].x + "%", top: N[start].y + "%" }}
          >
            A
          </span>
        )}
        {end && (
          <span
            className="pin b"
            style={{ left: N[end].x + "%", top: N[end].y + "%" }}
          >
            B
          </span>
        )}
        {selectedFacility && (
          <div className="card">
            <button onClick={() => setSelectedFacility(null)}>×</button>
            <span>⌖</span>
            <div>
              <small>{selectedFacility.type.toUpperCase()} · MOCK</small>
              <h3>{selectedFacility.name}</h3>
              <p>{selectedFacility.location}</p>
              <dl>
                <div>
                  <dt>건물</dt>
                  <dd>{selectedFacility.building}</dd>
                </div>
                <div>
                  <dt>층수</dt>
                  <dd>{selectedFacility.floor}</dd>
                </div>
              </dl>
              <p>{selectedFacility.description}</p>
            </div>
          </div>
        )}
        <div className="legend">
          <span>
            <i /> 조명 확인 구간
          </span>
          <span>◎ 포탈</span>
          <span>▰ 셔틀</span>
          <span>↕ 엘리베이터</span>
        </div>
      </div>
      <FacilityFilter value={filter} onChange={setFilter} />
    </main>
  );
}
