import campus from '../../data/campus.json';
import { dijkstra } from './algorithms/dijkstra';

export const places = campus.nodes;
export const byId = Object.fromEntries(places.map(n => [n.id, n]));
export const position = n => ({ x: 80 + (n.longitude - 127.125) * 175000, y: 70 + (37.3235 - n.latitude) * 180000 });
export const links = campus.edges.map(e => ({ ...e, available: e.available !== false }));
export function distance(a, b) {
  const rad = Math.PI / 180;
  const dLat = (b.latitude - a.latitude) * rad;
  const dLon = (b.longitude - a.longitude) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLon / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}
export function findRoute(start, end, avoidStairs) {
  return dijkstra(places, links.filter(e => !avoidStairs || e.condition !== 'stair'), start, end,
    e => distance(byId[e.from], byId[e.to]));
}
