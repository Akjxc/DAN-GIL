import { useState } from "react";
import Header from "./components/Header";
import RouteSearch from "./components/RouteSearch";
import CampusMap from "./components/CampusMap";
import Chatbot from "./components/Chatbot";
import { nodes, selectable } from "./data/nodes";
import { facilities } from "./data/facilities";
import { calculateRoute } from "./algorithms/routeCalculator";
export default function App() {
  let places = nodes.filter((n) => selectable.includes(n.id));
  const [start, setStart] = useState("gate"),
    [end, setEnd] = useState("engineering"),
    [mode, setMode] = useState("safe"),
    [route, setRoute] = useState(null),
    [filter, setFilter] = useState("all"),
    [selectedFacility, setSelectedFacility] = useState(null);
  return (
    <div className="app">
      <Header />
      <div className="workspace">
        <RouteSearch
          {...{ places, start, end, setStart, setEnd, mode, setMode, route }}
          onSearch={() => setRoute(calculateRoute(start, end, mode))}
        />
        <CampusMap
          {...{
            route,
            mode,
            facilities,
            filter,
            setFilter,
            selectedFacility,
            setSelectedFacility,
            start,
            end,
          }}
        />
      </div>
      <footer className="about" id="about">
        <b>DKU SafePath</b>
        <span>학생과 보행약자를 위한 캠퍼스 이동 경험을 설계합니다.</span>
        <em>Prototype v1.0</em>
      </footer>
      <Chatbot />
    </div>
  );
}
