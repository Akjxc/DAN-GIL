import campus from '../../data/campus.json';

export const places = campus.nodes;
export const byId = Object.fromEntries(places.map(n => [n.id, n]));
export const position = n => ({ x: 80 + (n.longitude - 127.125) * 175000, y: 70 + (37.3235 - n.latitude) * 180000 });
export const links = campus.edges.map(e => ({ ...e, available: e.available !== false }));
export function routeMapSegments(nodes) {
  const segments = [];
  let segment = [];
  for (const node of nodes) {
    if (Number.isFinite(node.latitude) && Number.isFinite(node.longitude)) {
      segment.push(node);
    } else {
      if (segment.length > 1) segments.push(segment);
      segment = [];
    }
  }
  if (segment.length > 1) segments.push(segment);
  return segments;
}
