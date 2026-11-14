import campus from '../../data/campus.json';

export const places = campus.nodes;
export const byId = Object.fromEntries(places.map(n => [n.id, n]));
export const position = n => ({ x: 80 + (n.longitude - 127.125) * 175000, y: 70 + (37.3235 - n.latitude) * 180000 });
export const links = campus.edges.map(e => ({ ...e, available: e.available !== false }));

export function routeExceptionLabel(edge) {
  if (edge.is_exception !== true) return null;
  if (edge.kind === 'outdoorPath') {
    return edge.condition === 'stair' ? '예외 실외 계단 구간' : '예외 실외 구간';
  }
  return edge.condition === 'stair' ? '예외 계단 구간' : null;
}

export function routeMapSegments(nodes, edges) {
  const segments = [];
  const hasCoordinates = node => Number.isFinite(node.latitude) && Number.isFinite(node.longitude);
  let segment;
  for (const [index, edge] of edges.entries()) {
    const from = nodes[index];
    const to = nodes[index + 1];
    if (!hasCoordinates(from) || !hasCoordinates(to)) {
      segment = undefined;
      continue;
    }
    const highlightedException = Boolean(routeExceptionLabel(edge));
    if (segment && segment.highlightedException === highlightedException) {
      segment.nodes.push(to);
    } else {
      segment = { nodes: [from, to], highlightedException };
      segments.push(segment);
    }
  }
  return segments;
}
