import { useEffect, useRef, useState } from "react";
import { nodes } from "../data/nodes";
import { buildings } from "../data/buildings";
import { modes } from "../algorithms/routeCalculator";
import { loadKakaoMapSdk, mockPositionToLatLng } from "../services/mapService";
import FacilityFilter from "./FacilityFilter";

const nodeById = Object.fromEntries(nodes.map((node) => [node.id, node]));

function createLabel(className, text, subText) {
  const element = document.createElement("div");
  element.className = className;
  const title = document.createElement("strong");
  title.textContent = text;
  element.appendChild(title);
  if (subText) {
    const sub = document.createElement("small");
    sub.textContent = subText;
    element.appendChild(sub);
  }
  return element;
}

export default function KakaoCampusMap({
  route,
  mode,
  facilities,
  filter,
  setFilter,
  selectedFacility,
  setSelectedFacility,
  start,
  end,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const mapsRef = useRef(null);
  const overlaysRef = useRef([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadKakaoMapSdk()
      .then((maps) => {
        if (cancelled || !containerRef.current) return;
        mapsRef.current = maps;
        mapRef.current = new maps.Map(containerRef.current, {
          center: new maps.LatLng(37.3213, 127.1277),
          level: 4,
        });
        mapRef.current.addControl(
          new maps.ZoomControl(),
          maps.ControlPosition.RIGHT,
        );
        setStatus("ready");
      })
      .catch((sdkError) => {
        setError(sdkError.message);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (status !== "ready") return;
    const maps = mapsRef.current;
    const map = mapRef.current;
    overlaysRef.current.forEach((overlay) => overlay.setMap(null));
    overlaysRef.current = [];
    const add = (overlay) => {
      overlay.setMap(map);
      overlaysRef.current.push(overlay);
    };

    buildings.forEach((building) => {
      add(
        new maps.CustomOverlay({
          position: mockPositionToLatLng(maps, building),
          content: createLabel(
            `kakao-building-label ${building.tone || ""}`,
            building.name,
            building.sub,
          ),
          yAnchor: 0.5,
          zIndex: 2,
        }),
      );
    });

    nodes
      .filter((node) => ["portal", "shuttle", "elevator"].includes(node.type))
      .forEach((node) => {
        const symbol =
          node.type === "portal" ? "◎" : node.type === "shuttle" ? "▰" : "↕";
        const content = createLabel(
          `kakao-special-marker ${node.type}`,
          symbol,
        );
        content.title = node.name;
        add(
          new maps.CustomOverlay({
            position: mockPositionToLatLng(maps, node),
            content,
            zIndex: 5,
          }),
        );
      });

    facilities
      .filter((facility) => filter === "all" || facility.type === filter)
      .forEach((facility) => {
        const content = createLabel("kakao-facility-marker", "●");
        content.title = facility.name;
        content.addEventListener("click", () => setSelectedFacility(facility));
        add(
          new maps.CustomOverlay({
            position: mockPositionToLatLng(maps, facility),
            content,
            zIndex: 7,
          }),
        );
      });

    if (route?.path?.length) {
      const path = route.path
        .map((id) => nodeById[id])
        .filter(Boolean)
        .map((node) => mockPositionToLatLng(maps, node));
      if (path.length > 1) {
        add(
          new maps.Polyline({
            path,
            strokeWeight: 8,
            strokeColor: "#ffffff",
            strokeOpacity: 0.9,
            strokeStyle: "solid",
            zIndex: 8,
          }),
        );
        add(
          new maps.Polyline({
            path,
            strokeWeight: 5,
            strokeColor: modes[mode].color,
            strokeOpacity: 1,
            strokeStyle: "solid",
            zIndex: 9,
          }),
        );
        const bounds = new maps.LatLngBounds();
        path.forEach((position) => bounds.extend(position));
        map.setBounds(bounds, 80, 80, 80, 380);
      }
    }

    [
      { id: start, label: "A", className: "start" },
      { id: end, label: "B", className: "end" },
    ].forEach(({ id, label, className }) => {
      const node = nodeById[id];
      if (!node) return;
      add(
        new maps.CustomOverlay({
          position: mockPositionToLatLng(maps, node),
          content: createLabel(`kakao-endpoint ${className}`, label),
          yAnchor: 1.2,
          zIndex: 10,
        }),
      );
    });

    return () => {
      overlaysRef.current.forEach((overlay) => overlay.setMap(null));
      overlaysRef.current = [];
    };
  }, [
    status,
    route,
    mode,
    facilities,
    filter,
    setSelectedFacility,
    start,
    end,
  ]);

  return (
    <main className="map">
      <header>
        <b>
          <i /> 단국대학교 죽전캠퍼스
        </b>
        <span>Kakao Map · 교내 경로는 프로젝트 데이터</span>
      </header>
      <div className="canvas kakao-map-shell">
        <div ref={containerRef} className="kakao-map-canvas" />
        {status === "loading" && (
          <div className="map-state">카카오맵을 불러오는 중입니다…</div>
        )}
        {status === "error" && (
          <div className="map-state error">
            <b>지도를 불러오지 못했습니다.</b>
            <span>{error}</span>
          </div>
        )}
        <div className="kakao-data-notice">
          건물·교내 경로 좌표는 현재 조감도 기반 임시 위치입니다.
        </div>
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
      </div>
      <FacilityFilter value={filter} onChange={setFilter} />
    </main>
  );
}
