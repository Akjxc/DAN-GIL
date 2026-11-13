import { dijkstra } from "./dijkstra";
import { nodes } from "../data/nodes";
import { edges } from "../data/edges";
export const modes = {
  fast: {
    label: "최단 시간",
    color: "#246bfd",
    icon: "⚡",
    desc: "예상 이동시간 우선",
  },
  safe: {
    label: "안심 야간",
    color: "#13a26b",
    icon: "✦",
    desc: "조명 확인 구간 우선",
  },
  walk: {
    label: "최소 보행",
    color: "#7856d8",
    icon: "↗",
    desc: "실제 걷는 거리 우선",
  },
};
const W = (m) => (e) =>
  m === "fast"
    ? e.time + (e.waitTime || 0)
    : m === "safe"
      ? e.time +
        ({ confirmed: 1, partial: 4, none: 12 }[e.lighting] || 5) +
        (e.stairs ? 3 : 0)
      : e.walkingDistance +
        (e.transport === "walk" ? 0 : -Math.min(e.walkingDistance * 0.45, 70)) +
        (e.waitTime || 0) * 3;
export function calculateRoute(s, t, m) {
  let r = dijkstra(nodes, edges, s, t, W(m));
  return (
    r && {
      ...r,
      time: r.edges.reduce((a, e) => a + e.time + (e.waitTime || 0), 0),
      walking: r.edges.reduce((a, e) => a + e.walkingDistance, 0),
    }
  );
}
