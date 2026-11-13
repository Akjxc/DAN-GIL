export function dijkstra(nodes, edges, start, end, weight) {
  const d = Object.fromEntries(nodes.map((n) => [n.id, Infinity])),
    prev = {},
    q = new Set(nodes.map((n) => n.id));
  d[start] = 0;
  while (q.size) {
    let u = [...q].reduce((a, b) => (d[a] < d[b] ? a : b));
    if (d[u] === Infinity) break;
    q.delete(u);
    if (u === end) break;
    edges
      .filter((e) => e.available && (e.from === u || e.to === u))
      .forEach((e) => {
        let v = e.from === u ? e.to : e.from;
        if (!q.has(v)) return;
        let a = d[u] + weight(e);
        if (a < d[v]) {
          d[v] = a;
          prev[v] = { u, e };
        }
      });
  }
  if (start !== end && !prev[end]) return null;
  let path = [end],
    used = [],
    u = end;
  while (u !== start) {
    let p = prev[u];
    if (!p) return null;
    used.unshift(p.e);
    u = p.u;
    path.unshift(u);
  }
  return { path, edges: used, cost: d[end] };
}
