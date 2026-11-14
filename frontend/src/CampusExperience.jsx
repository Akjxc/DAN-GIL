import { useEffect, useRef, useState } from 'react';
import { places, byId, position, links, routeMapSegments } from './campusGraph';
import { loadKakaoMapSdk, hasKakaoMapKey } from './services/mapService';
import { sendChatMessage } from './services/chatService';
import { requestPlaces, requestRoute } from './services/routeService';

const modes = [{ id: 'accessible', icon: '♿', name: '계단 없는 경로', sub: '엘리베이터·연결 통로', color: '#8660d9' }, { id: 'indoor', icon: (<svg viewBox="0 0 28 28" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 24V6l8-3 8 3v18M3 24h22M11 24v-6h6v6"/><path d="M10 9h1m6 0h1m-8 4h1m6 0h1"/></svg>), name: '실내 위주', sub: '실외 구간 최소화', color: '#169d78' }, { id: 'shortest', icon: (<svg viewBox="0 0 28 28" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="6" cy="22" r="3"/><circle cx="22" cy="6" r="3"/><path d="M8.5 19.5l11-11M12 8h6v6"/><path d="M4 14V7a3 3 0 0 1 3-3h7M14 24h7a3 3 0 0 0 3-3v-7" strokeOpacity=".25"/></svg>), name: '최단 경로', sub: '거리 기준', color: '#3778f6' }];
const STAIR_EXCEPTION_COLOR = '#b45309';
const LANDMARK_LABELS = {
  mainGate: null,
  bearStatue: null,
  parkingJc: '주차빌딩 앞',
  labJc: '종합실험동 앞',
  hyeDangYardJc: '노천마당 앞',
  dentalJc: '치과대학 방면',
};


function LiveMap({ route, start, end, showEntrances, filter, onPick, onError }) {
  const el = useRef(null);
  const [map, setMap] = useState(null);
  useEffect(() => {
    let cancelled = false;
    loadKakaoMapSdk().then(m => {
      if (cancelled) return;
      const instance = new m.Map(el.current, { center: new m.LatLng(37.3214, 127.1276), level: 3 });
      instance.addControl(new m.ZoomControl(), m.ControlPosition.RIGHT);
      setMap({ m, instance });
    }).catch(onError);
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (!map) return;
    const { m, instance } = map;
    const overlays = [];
    const candidates = route ? route.nodes : places;
    candidates.filter(n => Number.isFinite(n.latitude) && Number.isFinite(n.longitude))
      .filter(n => [start, end].includes(n.id) || (showEntrances && (filter === 'all' || (filter === 'entrance' ? n.kind === 'entrance' : n.kind === 'outdoorPath')))).forEach(n => {
      const button = document.createElement('button');
      button.className = 'live-pin';
      if (n.kind === 'outdoorPath' && ![start, end].includes(n.id)) {
        button.classList.add('junction-pin');
        const dot = document.createElement('span');
        dot.className = 'junction-dot';
        button.appendChild(dot);
      }
      const label = document.createElement('span');
      label.textContent = n.id === start ? 'A · ' + n.name : n.id === end ? 'B · ' + n.name : n.name;
      button.appendChild(label);
      button.onclick = () => onPick(n.id);
      overlays.push(new m.CustomOverlay({ map: instance, position: new m.LatLng(n.latitude, n.longitude), content: button, yAnchor: button.classList.contains('junction-pin') ? 0.5 : 1, xAnchor: button.classList.contains('junction-pin') ? 0 : 0.5, zIndex: [start, end].includes(n.id) ? 10 : 5 }));
    });
    if (route?.mapSegments.length) {
      const bounds = new m.LatLngBounds();
      for (const { nodes, stairException } of route.mapSegments) {
        const path = nodes.map(n => new m.LatLng(n.latitude, n.longitude));
        overlays.push(new m.Polyline({ map: instance, path, strokeWeight: 6, strokeColor: stairException ? STAIR_EXCEPTION_COLOR : '#3778f6', strokeOpacity: 1 }));
        path.forEach(p => bounds.extend(p));
      }
      instance.setBounds(bounds);
    }
    if (route) {
      const mappedNodes = route.nodes.filter(n => Number.isFinite(n.latitude) && Number.isFinite(n.longitude));
      mappedNodes.slice(1, -1).forEach((node, index) => {
        const position = new m.LatLng(node.latitude, node.longitude);

        const marker = document.createElement('div');
        marker.className = 'route-turn-marker';
        const dot = document.createElement('span');
        dot.className = 'route-turn-dot';
        const label = document.createElement('button');
        label.className = 'route-turn-label';
        label.textContent = node.name;
        label.onclick = () => onPick(node.id);
        marker.append(dot, label);
        overlays.push(new m.CustomOverlay({
          map: instance,
          position,
          content: marker,
          xAnchor: 0,
          yAnchor: 0.5,
          zIndex: 12,
        }));
      });
    }
    const resize = new ResizeObserver(() => instance.relayout());
    resize.observe(el.current);
    return () => { overlays.forEach(o => o.setMap(null)); resize.disconnect(); };
  }, [map, route, start, end, showEntrances, filter, onPick]);
  return <div className="live-map" ref={el} />;
}

function buildGuidance(route, names) {
  const steps = [];
  for (let i = 0; i < route.edges.length; i++) {
    const edge = route.edges[i];
    let endIndex = i + 1;
    if (edge.condition === 'elevator' || edge.condition === 'stair') {
      while (endIndex < route.edges.length && route.edges[endIndex].condition === edge.condition) endIndex++;
    }
    const destination = names[route.path[endIndex]];
    const last = endIndex === route.path.length - 1;
    const floor = destination?.floor;
    const floorLabel = floor == null ? '' : floor < 0 ? '지하 ' + Math.abs(floor) + '층' : floor + '층';
    const transport = edge.condition === 'elevator' ? '엘리베이터' : edge.condition === 'stair' ? '계단' : null;
    const stairException = edge.condition === 'stair' && route.edges.slice(i, endIndex).some(segment => segment.is_exception);
    steps.push({
      label: stairException ? '예외 계단 구간' : last ? '도착' : transport || (edge.kind === 'indoorPath' ? '실내 이동' : '실외 이동'),
      stairException,
      title: last ? destination.name + '에 도착합니다.' : transport && floorLabel ? transport + '로 ' + floorLabel + '까지 이동하세요.' : destination.name + (transport ? '에서 ' + transport + '를 이용하세요.' : ' 방향으로 이동하세요.'),
      detail: edge.condition === 'slope' ? '경사 구간' : !transport && !last && edge.kind === 'indoorPath' ? '연결된 복도를 따라 이동합니다.' : null,
    });
    i = endIndex - 1;
  }
  return steps;
}


export default function CampusExperience() {
  const [start, setStart] = useState('humanityEntranceF1');
  const [end, setEnd] = useState('libraryEntranceF1');
  const [mode, setMode] = useState('shortest');
  const avoid = mode === 'accessible';
  const [route, setRoute] = useState(null);
  const [searched, setSearched] = useState(false);
  const [routeBusy, setRouteBusy] = useState(false);
  const [routeError, setRouteError] = useState('');
  const [routePlaces, setRoutePlaces] = useState(places);
  const [placesError, setPlacesError] = useState('');
  const routeRequest = useRef(null);
  const routeRevision = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    requestPlaces(controller.signal)
      .then(nodes => { if (!controller.signal.aborted) setRoutePlaces(nodes); })
      .catch(() => { if (!controller.signal.aborted) setPlacesError('실내 장소 목록을 불러오지 못했어요. 백엔드 실행 상태를 확인한 뒤 새로고침해 주세요.'); });
    return () => {
      controller.abort();
      routeRequest.current?.abort();
    };
  }, []);
  const [selected, setSelected] = useState(null);
  const [showEntrances, setShowEntrances] = useState(() => localStorage.getItem('safepath-show-entrances') === 'true');
  useEffect(() => { localStorage.setItem('safepath-show-entrances', String(showEntrances)); }, [showEntrances]);

  const [filter, setFilter] = useState('all');
  const [zoom, setZoom] = useState(1);
  const [live, setLive] = useState(hasKakaoMapKey());
  const [mapError, setMapError] = useState('');
  const [about, setAbout] = useState(false);
  const [chat, setChat] = useState(false);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([{ role: 'bot', text: '안녕하세요! 캠퍼스에서 어디로 가시나요?', local: true }]);
  const routeNames = { ...byId, ...Object.fromEntries(routePlaces.map(n => [n.id,n])), ...Object.fromEntries((route?.nodes || []).map(n => [n.id,n])) };
  const selectedPlace = routeNames[selected];
  const endpointOptions = Object.values(routeNames).filter(n =>
    n.kind === 'entrance' || Object.hasOwn(LANDMARK_LABELS, n.id) || n.id === start || n.id === end,
  );
  const chosenMode = modes.find(m => m.id === mode);
  const visible = (route ? route.nodes : places).filter(n => Number.isFinite(n.latitude) && Number.isFinite(n.longitude)).filter(n => [start, end].includes(n.id) || (showEntrances && (filter === 'all' || (filter === 'entrance' ? n.kind === 'entrance' : n.kind === 'outdoorPath'))));
  const clear = () => {
    routeRevision.current++;
    routeRequest.current?.abort();
    routeRequest.current = null;
    setRouteBusy(false);
    setRouteError('');
    setRoute(null);
    setSearched(false);
  };
  const choose = (setter, value) => { setter(value); clear(); };
  function displayRoute(result, source) {
    const nodes = result?.nodes.map(node => ({ ...byId[node.id], ...node }));
    setRoute(result && {
      ...result,
      nodes,
      source,
      path: nodes.map(node => node.id),
      mapSegments: routeMapSegments(nodes, result.edges),
    });
    setSelected(null);
    setSearched(true);
  }
  async function search() {
    clear();
    const controller = new AbortController();
    routeRequest.current = controller;
    setRouteBusy(true);
    try {
      const result = await requestRoute(start, end, avoid, controller.signal, mode);
      if (controller.signal.aborted) return;
      displayRoute(result, 'search');
    } catch (error) {
      if (!controller.signal.aborted) {
        setRouteError(error instanceof TypeError ? '경로 서버에 연결하지 못했어요. 백엔드 실행 상태를 확인해 주세요.' : error.message);
      }
    } finally {
      if (!controller.signal.aborted) {
        routeRequest.current = null;
        setRouteBusy(false);
      }
    }
  }
  async function send(event) {
    event.preventDefault();
    if (!input.trim() || busy) return;
    const text = input.trim(); setInput(''); setBusy(true);
    const revision = routeRevision.current;
    setMessages(m => [...m, { role: 'user', text }]);
    try {
      const answer = await sendChatMessage(text, messages);
      setMessages(m => [...m, { role: 'bot', text: answer.message, local: answer.status === 'error' }]);
      if (revision === routeRevision.current) {
        if (answer.status === 'route' && answer.route?.nodes.length) {
          clear();
          setStart(answer.route.nodes[0].id);
          setEnd(answer.route.nodes.at(-1).id);
          displayRoute(answer.route, 'chat');
        } else if (answer.status === 'no_route' && route?.source === 'chat') {
          clear();
        }
      }
    } catch (error) {
      setMessages(m => [...m, { role: 'bot', text: error.message, local: true }]);
    } finally {
      setBusy(false);
    }
  }
  return <div className="experience">
<header className="topbar"><a className="brand" href="#"><span className="brand-symbol d-path-logo"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M13 10h10c10 0 16 5 16 14s-6 14-16 14H13V10Z" fill="none" stroke="white" strokeWidth="4" strokeLinejoin="round"/><path d="M13 31h9V20h10" fill="none" stroke="#8ee4d2" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/><circle cx="13" cy="31" r="3" fill="white"/><circle cx="32" cy="20" r="3.5" fill="#8ee4d2"/></svg></span><span className="brand-wordmark"><b>DAN-GIL</b><small>단국대학교 캠퍼스 길찾기</small></span></a><span className="campus-badge"><i /> 죽전캠퍼스</span></header>
    <div className="page-heading"><div><span className="eyebrow">YOUR CAMPUS, YOUR WAY</span><h1>우리의 캠퍼스, 더 편안한 한 걸음.</h1><p>출입구부터 연결 통로까지, 나에게 맞는 길을 찾아보세요.</p></div><div className="heading-mark">DKU<span>WALK BETTER.</span></div></div>
    <div className="map-workspace">
<aside className="search-panel"><div className="panel-title"><span className="mini-icon"><svg viewBox="0 0 28 28" width="29" height="29" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M22 11c0 6-8 12-8 12S6 17 6 11a8 8 0 1 1 16 0Z"/><circle cx="14" cy="11" r="2.8"/><path d="M7 23c-2 0-3 1-3 2h20c0-1-1-2-3-2" strokeOpacity=".3"/></svg></span><div><h2>어디로 가시나요?</h2><p>캠퍼스 안의 길을 연결합니다</p></div></div>
        <div className="location-fields">
          {[[start, setStart, '출발지', 'A'], [end, setEnd, '도착지', 'B']].map(([value, setter, label, letter]) => (
            <label className="place-field" key={letter}>
              <span className={`letter ${letter}`}>{letter}</span>
              <span>
                <small>{label}</small>
                <select aria-label={label} value={value} onChange={e => choose(setter, e.target.value)}>
                  {endpointOptions.map(n => <option key={n.id} value={n.id}>{LANDMARK_LABELS[n.id] ?? n.name}</option>)}
                </select>
              </span>
            </label>
          ))}
          <button className="swap" aria-label="출발지와 도착지 바꾸기" onClick={() => { setStart(end); setEnd(start); clear(); }}>⇅</button>
        </div>
        {placesError && <p className="mode-warning" role="status">{placesError}</p>}
        <h3 className="section-label">이동 방식</h3><div className="mode-grid">{modes.map(m => <button key={m.id} className={mode === m.id ? 'mode selected' : 'mode'} onClick={() => choose(setMode, m.id)}><span>{m.icon}</span><b>{m.name}</b><small>{m.sub}</small></button>)}</div>
        {mode === 'accessible' && <p className="fine-print">휠체어 이용자를 위해 계단 구간을 제외하고 엘리베이터와 연결 통로를 이용합니다.</p>}
        {mode === 'indoor' && <p className="fine-print">실내 연결을 우선하며, 필요한 실외 구간은 함께 안내합니다.</p>}
        <button className="search-button" disabled={routeBusy} onClick={search}>{routeBusy ? '경로 계산 중…' : '경로 찾기'} <span>↗</span></button>
        {routeError && <p className="mode-warning" role="alert">경로를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>}
        <div className="results" aria-live="polite">
          {!searched ? <div className="empty-result"><span>⌁</span><b>다음 목적지를 정해보세요</b><p>출발지와 도착지를 선택하면<br/>이동 경로를 안내합니다.</p></div> :
            !route ? <p className="mode-warning">선택한 조건으로 이동할 수 있는 경로가 없습니다. 다른 출입구를 선택해 주세요.</p> :
            <><div className="result-heading"><b>{start === end ? '같은 장소입니다' : '추천 경로'}</b><span>{route.exception_notice ? '대안 경로' : route.source === 'chat' ? '챗봇 경로' : avoid ? '계단 제외' : '캠퍼스 길찾기'}</span></div>
              {route.exception_notice && <p className="mode-warning">{route.exception_notice}</p>}
              <div className="journey-endpoints"><p><span className="letter">A</span>{routeNames[start]?.name}</p><div className="journey-connector"/><p><span className="letter B">B</span>{routeNames[end]?.name}</p></div>
<div className="route-stats">{route.edges.some(e => e.condition === 'stair') && <span>계단 <b>{route.edges.filter(e => e.condition === 'stair').length}구간</b></span>}{route.edges.some(e => e.condition === 'slope') && <span>경사 <b>{route.edges.filter(e => e.condition === 'slope').length}구간</b></span>}{route.edges.some(e => e.condition === 'elevator') && <span><b>엘리베이터 이용</b></span>}</div>
            </>}
        </div>
        {route && <section className="walking-guide"><span className="eyebrow">단길 이동 안내</span><h3>목적지까지 이렇게 이동하세요</h3>
          <ol>{buildGuidance(route, routeNames).map((step, index) => <li key={index}><span className="guide-number">{String(index + 1).padStart(2, '0')}</span><div><small style={step.stairException ? { color: STAIR_EXCEPTION_COLOR } : undefined}>{step.label}</small><b>{step.title}</b>{step.detail && <p>{step.detail}</p>}</div></li>)}</ol>
        </section>}
      </aside>
      <main className="map-panel"><div className="map-toolbar"><div><i /> 단국대학교 <b>죽전캠퍼스</b><span className="map-kind">{live ? '카카오맵' : '좌표 기반 캠퍼스맵'}</span></div><button onClick={() => { if (hasKakaoMapKey()) setLive(v => !v); else setMapError('카카오 지도를 사용하려면 frontend/.env에 VITE_KAKAO_MAP_KEY를 설정해 주세요.'); }}>{live ? '캠퍼스맵 보기' : '카카오맵 보기'} ↗</button></div>
        <div className="map-surface">{live ? <LiveMap {...{route,start,end,showEntrances,filter}} onPick={setSelected} onError={e => { setMapError(e.message); setLive(false); }} /> : <div className="map-scroll"><svg className="campus-svg" viewBox="0 0 1060 960" style={{width: `${zoom * 100}%`, height: `${zoom * 100}%`}} aria-label="실제 입력 좌표로 배치한 캠퍼스 연결 지도">
          <defs><pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#cfdacf" /></pattern><filter id="pin-shadow"><feDropShadow dx="0" dy="4" stdDeviation="5" floodOpacity=".12" /></filter></defs><rect width="1060" height="960" fill="#edf2ea"/><rect width="1060" height="960" fill="url(#dots)"/><path d="M0 0H420Q120 220 110 480T0 950Z M780 0H1060V960H900Q710 780 870 500T780 0" fill="#dfebda"/><text x="870" y="840" className="park-label">캠퍼스 녹지</text><text x="50" y="890" className="north-label">N ↑</text>
          {links.map(e => { const a=position(byId[e.from]),b=position(byId[e.to]);return <g key={e.id}><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#d5ddd1" strokeWidth="21" strokeLinecap="round"/><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={e.kind === 'indoorPath' ? '#e3e1ee' : '#fff'} strokeWidth="14" strokeLinecap="round"/><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={e.condition==='stair'?'#d7a667': '#dce3db'} strokeWidth="2" strokeDasharray={e.condition==='stair'?'2 5':'4 8'}/></g>; })}
          {Object.entries(Object.groupBy(places.filter(n=>n.buildingId), n=>n.buildingId)).map(([id,ns]) => {const x=ns.reduce((s,n)=>s+position(n).x,0)/ns.length,y=ns.reduce((s,n)=>s+position(n).y,0)/ns.length;return <g key={id} className="map-building" transform={`translate(${x},${y})`}><rect x="-48" y="-27" width="96" height="54" rx="10"/><path d="M-38 -17H38M-38 -10H38" stroke="#dce3ec" strokeWidth="3"/><text y="7">{ns[0].name.split(/ [1-9지]/)[0]}</text></g>;})}
          {route?.mapSegments.map(({ nodes, stairException }) => {
            const points = nodes.map(node => { const p = position(node); return `${p.x},${p.y}`; }).join(' ');
            return <g key={nodes[0].id}><polyline points={points} fill="none" stroke="white" strokeWidth="13" strokeLinejoin="round" strokeLinecap="round"/><polyline points={points} fill="none" stroke={stairException ? STAIR_EXCEPTION_COLOR : route.source === 'chat' ? modes[0].color : chosenMode.color} strokeWidth="7" strokeLinejoin="round" strokeLinecap="round"/></g>;
          })}
          {visible.map(n=>{const p=position(n),active=[start,end].includes(n.id);return <g key={n.id} role="button" tabIndex="0" aria-label={n.name} onClick={()=>setSelected(n.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' ')setSelected(n.id);}} className="node-hit" transform={`translate(${p.x},${p.y})`}><title>{n.name}</title>{showEntrances && !active && <text className="route-place-label" y="-14" textAnchor="middle">{n.name}</text>}<circle r="14" fill="transparent"/><circle r={active?7:4} fill={active?'#3979ef':n.kind==='entrance'?'#fff':'#9eafa0'} stroke={active?'white':'#739281'} strokeWidth="2"/>{active&&<g transform="translate(0,-26)" filter="url(#pin-shadow)"><rect x="-18" y="-21" width="36" height="36" rx="13" fill={n.id===start?'#3478f6':'#142d4c'}/><text className="endpoint-text" y="3">{n.id===start?'A':'B'}</text></g>}</g>;})}
        </svg></div>}
        <div className="floating-map-label"><span>◉</span><div><b>죽전캠퍼스</b><small>{places.length}개 출입구·분기점 연결</small></div></div>
        {!live&&<div className="zoom-control"><button aria-label="확대" onClick={()=>setZoom(z=>Math.min(2,z+.25))}>+</button><button aria-label="축소" onClick={()=>setZoom(z=>Math.max(1,z-.25))}>−</button><button aria-label="지도 초기화" onClick={()=>setZoom(1)}>⌖</button></div>}
        {selectedPlace&&<div className="place-card"><button className="close-card" aria-label="장소 닫기" onClick={()=>setSelected(null)}>×</button><span className="eyebrow">{selectedPlace.kind==='entrance'?'BUILDING ENTRANCE':'CAMPUS WAYPOINT'}</span><h3>{selectedPlace.name}</h3><p>{selectedPlace.floor!=null?`${selectedPlace.floor}층 · `:''}사용자 제공 좌표</p><div><button onClick={()=>{choose(setStart,selected);setSelected(null);}}>출발지로</button><button onClick={()=>{choose(setEnd,selected);setSelected(null);}}>도착지로</button></div></div>}
        <div className="map-caption">{live?'Kakao Maps':'입력 좌표 기반 개략도 · 건물 도형은 실제 외곽선이 아닙니다'}</div></div>
        <div className="map-bottom"><button className="entrance-toggle" role="switch" aria-checked={showEntrances} onClick={() => { setShowEntrances(v => !v); setSelected(null); }}><span className={`toggle-track ${showEntrances ? 'on' : ''}`}><span /></span><span>{route ? '경로 장소' : '장소 이름'} {showEntrances ? '표시' : '숨김'}</span></button><div className="filter-buttons">{[['all','전체 보기'],['entrance','출입구'],['junction','분기점']].map(([id,label])=><button className={filter===id?'selected':''} key={id} onClick={()=>setFilter(id)}>{label}</button>)}</div><span><i className="legend-dot"/> 출입구 <i className="legend-line"/> 연결 보행로</span></div>
        {mapError&&<div className="map-feedback" role="status">{mapError}<button onClick={()=>setMapError('')} aria-label="알림 닫기">×</button></div>}
      </main>
    </div>
    <footer className="page-footer"><b>DKU SafePath</b><span>더 가까운 캠퍼스, 모두를 위한 이동.</span><small>단국대학교 학생 프로젝트 · Prototype</small></footer>
    {about&&<div className="modal-backdrop" onClick={()=>setAbout(false)}><section role="dialog" aria-modal="true" aria-label="서비스 소개" className="about-dialog" onClick={e=>e.stopPropagation()}><button onClick={()=>setAbout(false)} aria-label="닫기">×</button><span className="eyebrow">ABOUT SAFEPATH</span><h2>모두에게 열린 캠퍼스를 위해.</h2><p>DKU SafePath는 학생과 보행약자의 이동을 돕는 캠퍼스 길찾기 프로젝트입니다. 사용자 제공 좌표와 팀이 작성한 연결 정보를 활용합니다.</p><p>등록된 실외·실내 통로와 층간 연결을 바탕으로 경로를 계산합니다. 실내 이동은 경로 목록에서 확인할 수 있어요.</p></section></div>}
    <button className="chat-launch" aria-label="채팅 도우미 열기" onClick={()=>setChat(v=>!v)}>{chat?'×':'✦'}<span>캠퍼스 도우미</span></button>
    {chat&&<section className="chat-window" aria-label="캠퍼스 도우미"><header><span>✦ 캠퍼스 도우미</span><button aria-label="채팅 닫기" onClick={()=>setChat(false)}>×</button></header><div className="messages" aria-live="polite">{messages.map((m,i)=><p key={i} className={m.role}>{m.text}</p>)}{busy&&<p>답변을 준비하고 있어요…</p>}</div><form onSubmit={send}><input aria-label="질문" placeholder="캠퍼스에 대해 물어보세요" value={input} maxLength={4000} onChange={e=>setInput(e.target.value)}/><button disabled={busy||!input.trim()} aria-label="질문 보내기">↑</button></form></section>}
  </div>;
}
