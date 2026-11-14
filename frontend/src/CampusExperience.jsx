import { useEffect, useRef, useState } from 'react';
import { places, byId, position, links } from './campusGraph';
import { loadKakaoMapSdk, hasKakaoMapKey } from './services/mapService';
import { requestRoute } from './services/routeService';
import { sendChatMessage } from './services/chatService';

const modes = [{ id: 'fast', icon: '↗', name: '짧은 경로', sub: '백엔드 조건 비용', color: '#3778f6' }, { id: 'safe', icon: '☾', name: '안심 야간', sub: '조명 정보 준비 중', color: '#169d78' }, { id: 'walk', icon: '♧', name: '최소 보행', sub: '이동수단 정보 준비 중', color: '#8660d9' }];

function LiveMap({ route, start, end, showEntrances, onPick, onError }) {
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
    places.filter(n => (showEntrances && n.kind === 'entrance') || [start, end].includes(n.id)).forEach(n => {
      const button = document.createElement('button');
      button.className = 'live-pin';
      button.textContent = n.id === start ? 'A · 출발' : n.id === end ? 'B · 도착' : n.name;
      button.onclick = () => onPick(n.id);
      overlays.push(new m.CustomOverlay({ map: instance, position: new m.LatLng(n.latitude, n.longitude), content: button, yAnchor: 1 }));
    });
    if (route) {
      const path = route.nodes.filter(n => Number.isFinite(n.latitude) && Number.isFinite(n.longitude)).map(n => new m.LatLng(n.latitude, n.longitude));
      overlays.push(new m.Polyline({ map: instance, path, strokeWeight: 6, strokeColor: '#3778f6', strokeOpacity: 1 }));
      const bounds = new m.LatLngBounds();
      path.forEach(p => bounds.extend(p));
      if (path.length > 1) instance.setBounds(bounds);
    }
    const resize = new ResizeObserver(() => instance.relayout());
    resize.observe(el.current);
    return () => { overlays.forEach(o => o.setMap(null)); resize.disconnect(); };
  }, [map, route, start, end, showEntrances, onPick]);
  return <div className="live-map" ref={el} />;
}

export default function CampusExperience() {
  const [start, setStart] = useState('humanityEntranceF1');
  const [end, setEnd] = useState('libraryEntranceF1');
  const [mode, setMode] = useState('fast');
  const [avoid, setAvoid] = useState(false);
  const [route, setRoute] = useState(null);
  const [searched, setSearched] = useState(false);
  const [routeBusy, setRouteBusy] = useState(false);
  const [routeError, setRouteError] = useState('');
  const requestRef = useRef(null);
  useEffect(() => () => requestRef.current?.abort(), []);
  const routeNames = { ...byId, ...Object.fromEntries((route?.nodes || []).map(n => [n.id, n])) };
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
  const [messages, setMessages] = useState([{ role: 'bot', text: '안녕하세요! 단길 캠퍼스 도우미예요. 출발지와 목적지, 층 또는 출입구를 알려주세요. 계단 제외 같은 이동 조건도 함께 말씀해 주세요.' }]);
  const chosenMode = modes.find(m => m.id === mode);
  const visible = places.filter(n => [start, end].includes(n.id) || ((showEntrances || n.kind !== 'entrance') && (filter === 'all' || (filter === 'entrance' ? n.kind === 'entrance' : n.kind !== 'entrance'))));
  const points = route?.nodes.filter(n => Number.isFinite(n.latitude) && Number.isFinite(n.longitude)).map(n => { const p = position(n); return `${p.x},${p.y}`; }).join(' ');
  const clear = () => { requestRef.current?.abort(); setRouteBusy(false); setRouteError(''); setRoute(null); setSearched(false); };
  const choose = (setter, value) => { setter(value); clear(); };
  const search = async () => {
    requestRef.current?.abort();
    const controller = new AbortController(); requestRef.current = controller;
    setRouteBusy(true); setRouteError(''); setRoute(null); setSearched(false);
    try { const result = await requestRoute(start, end, avoid, controller.signal); if (!controller.signal.aborted) { setRoute(result); setSearched(true); } }
    catch (error) { if (!controller.signal.aborted) setRouteError(error.message); }
    finally { if (!controller.signal.aborted) setRouteBusy(false); }
  };
  async function send(event) {
    event.preventDefault();
    if (!input.trim() || busy) return;
    const text = input.trim(); setInput(''); setBusy(true);
    setMessages(m => [...m, { role: 'user', text }]);
    const history = messages.filter((m, index) => index > 0 && !m.error).map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text }));
    try {
      const answer = await sendChatMessage(text, history);
      setMessages(m => [...m, { role: 'bot', text: answer.message, error: answer.status === 'error' }]);
    }
    catch (error) { setMessages(m => [...m, { role: 'bot', text: error.message, error: true }]); }
    finally { setBusy(false); }
  }
  return <div className="experience">
<header className="topbar"><a className="brand" href="#"><span className="brand-symbol d-path-logo"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M13 10h10c10 0 16 5 16 14s-6 14-16 14H13V10Z" fill="none" stroke="white" strokeWidth="4" strokeLinejoin="round"/><path d="M13 31h9V20h10" fill="none" stroke="#8ee4d2" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/><circle cx="13" cy="31" r="3" fill="white"/><circle cx="32" cy="20" r="3.5" fill="#8ee4d2"/></svg></span><span className="brand-wordmark"><b>단길</b><small>DKU SafePath <span>· 캠퍼스를 잇는 길</span></small></span></a><nav><button className="active" onClick={() => setAbout(false)}>길찾기</button><button onClick={() => { setFilter('entrance'); setAbout(false); }}>출입구 찾기</button><button onClick={() => setAbout(true)}>서비스 소개</button></nav><span className="campus-badge"><i /> 죽전캠퍼스</span></header>
    <div className="page-heading"><div><span className="eyebrow">YOUR CAMPUS, YOUR WAY</span><h1>우리의 캠퍼스, 더 편안한 한 걸음.</h1><p>출입구부터 연결 통로까지, 나에게 맞는 길을 찾아보세요.</p></div><div className="heading-mark">DKU<span>WALK BETTER.</span></div></div>
    <div className="map-workspace">
      <aside className="search-panel"><div className="panel-title"><span className="mini-icon">⌁</span><div><h2>어디로 가시나요?</h2><p>캠퍼스 안의 길을 연결합니다</p></div></div>
<div className="location-fields">{[[start, setStart, '출발지', 'A'], [end, setEnd, '도착지', 'B']].map(([value, setter, label, letter]) => <label className="place-field" key={letter}><span className={`letter ${letter}`}>{letter}</span><span><small>{label}</small><select aria-label={label} value={value} onChange={e => choose(setter, e.target.value)}>{places.filter(n => !n.name.includes('분기점')).map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></span></label>)}<button className="swap" aria-label="출발지와 도착지 바꾸기" onClick={() => { setStart(end); setEnd(start); clear(); }}>⇅</button></div>
        <h3 className="section-label">이동 방식</h3><div className="mode-grid">{modes.map(m => <button key={m.id} className={mode === m.id ? 'mode selected' : 'mode'} onClick={() => choose(setMode, m.id)}><span>{m.icon}</span><b>{m.name}</b><small>{m.sub}</small></button>)}</div>
<label className="check-row"><input type="checkbox" checked={avoid} onChange={e => choose(setAvoid, e.target.checked)} /><span>계단 없는 경로 우선</span><span className="option-tag">접근성</span></label><p className="fine-print">계단이 없는 휠체어 전용길입니다. 실제 휠체어 통행 가능 여부는 현장에서 확인해 주세요.</p>
        {mode !== 'fast' && <p className="mode-warning">{mode === 'safe' ? '조명 데이터가 없어 야간 안전성을 평가할 수 없습니다.' : '운행·대기시간 데이터가 없어 최소 보행을 계산할 수 없습니다.'} 현재는 동일한 백엔드 조건 비용 기준 경로를 보여줍니다.</p>}
        <button className="search-button" disabled={routeBusy} onClick={search}>{routeBusy ? '경로 계산 중…' : '경로 찾기'} <span>↗</span></button>
        {routeError && <p className="mode-warning" role="alert">{routeError}</p>}<div className="results" aria-live="polite">{!searched ? <div className="empty-result"><span>⌁</span><b>다음 목적지를 정해보세요</b><p>출발지와 도착지를 선택하면<br />지도에 연결 경로가 표시됩니다.</p></div> : !route ? <p className="mode-warning">조건에 맞는 연결 경로가 없습니다. 계단 제외 옵션을 해제하거나 다른 출입구를 선택해 주세요.</p> : <><div className="result-heading"><b>{start === end ? '같은 장소입니다' : '추천 연결 경로'}</b><span>백엔드 계산</span></div><div className="route-metric">{route.cost}<small>점</small><span>조건별 시연용 비용 합계</span></div><p className="fine-print">백엔드가 실내·실외 연결을 함께 계산합니다. 평지 1·경사 2·계단 3·엘리베이터 2의 시연용 비용이며, 실측 거리·시간이 아닙니다.</p><div className="route-stats"><span>계단 <b>{route.edges.filter(e => e.condition === 'stair').length}구간</b></span><span>경사 <b>{route.edges.filter(e => e.condition === 'slope').length}구간</b></span></div><ol className="route-steps">{route.path.map((id,i) => <li key={id}><span>{i === 0 ? 'A' : i === route.path.length - 1 ? 'B' : '·'}</span>{routeNames[id]?.name || id}</li>)}</ol></>}</div>
        {route && <section className="walking-guide"><span className="eyebrow">YOUR NEXT STEP</span><h3>이렇게 이동해 보세요</h3><p className="guide-intro">{byId[start].name}에서 출발해<br/><strong>{byId[end].name}</strong>까지 이어지는 길이에요.</p><ol>{route.edges.map((edge, index) => {
          const destination = routeNames[route.path[index + 1]];
          const isLast = index === route.edges.length - 1;
          const detail = edge.condition === 'stair' ? '계단을 이용하는 구간이에요. 발밑에 주의해 주세요.' : edge.condition === 'elevator' ? '엘리베이터를 이용해 다음 층으로 이동해 주세요.' : edge.condition === 'slope' ? '경사가 있는 구간이에요. 속도를 천천히 조절해 주세요.' : edge.kind === 'indoorPath' ? '건물 안 연결 통로를 따라 이동해 주세요.' : '평지 연결 구간을 따라 이동해 주세요.';
          return <li key={edge.id}><span className="guide-number">{String(index + 1).padStart(2, '0')}</span><div><small>{isLast ? '목적지 도착' : edge.kind === 'indoorPath' ? '실내 연결' : '실외 이동'} · {edge.condition === 'stair' ? '계단' : edge.condition === 'slope' ? '경사' : edge.condition === 'elevator' ? '엘리베이터' : '평지'}</small><b>{destination.name}{isLast ? '에 도착해요.' : ' 방향으로 이동하세요.'}</b><p>{detail}</p></div></li>;
        })}</ol><p className="fine-print">등록된 연결 순서 안내입니다. 좌·우회전, 계단의 상·하행 방향과 현장 표지판은 직접 확인해 주세요.</p></section>}
        <div className="panel-note"><span>ⓘ</span><p>교내 연결 정보를 바탕으로 한 시범 서비스입니다. 실제 통행 가능 여부를 현장에서 확인해 주세요.</p></div>
      </aside>
      <main className="map-panel"><div className="map-toolbar"><div><i /> 단국대학교 <b>죽전캠퍼스</b><span className="map-kind">{live ? '카카오맵' : '좌표 기반 캠퍼스맵'}</span></div><button onClick={() => { if (hasKakaoMapKey()) setLive(v => !v); else setMapError('카카오 지도를 사용하려면 frontend/.env에 VITE_KAKAO_MAP_KEY를 설정해 주세요.'); }}>{live ? '캠퍼스맵 보기' : '카카오맵 보기'} ↗</button></div>
<div className="map-surface">{live ? <LiveMap {...{route,start,end,showEntrances}} onPick={setSelected} onError={e => { setMapError(e.message); setLive(false); }} /> : <div className="map-scroll"><svg className="campus-svg" viewBox="0 0 1060 960" style={{width: `${zoom * 100}%`, height: `${zoom * 100}%`}} aria-label="실제 입력 좌표로 배치한 캠퍼스 연결 지도">
          <defs><pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#cfdacf" /></pattern><filter id="pin-shadow"><feDropShadow dx="0" dy="4" stdDeviation="5" floodOpacity=".12" /></filter></defs><rect width="1060" height="960" fill="#edf2ea"/><rect width="1060" height="960" fill="url(#dots)"/><path d="M0 0H420Q120 220 110 480T0 950Z M780 0H1060V960H900Q710 780 870 500T780 0" fill="#dfebda"/><text x="870" y="840" className="park-label">캠퍼스 녹지</text><text x="50" y="890" className="north-label">N ↑</text>
          {links.map(e => { const a=position(byId[e.from]),b=position(byId[e.to]);return <g key={e.id}><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#d5ddd1" strokeWidth="21" strokeLinecap="round"/><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={e.kind === 'indoorPath' ? '#e3e1ee' : '#fff'} strokeWidth="14" strokeLinecap="round"/><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={e.condition==='stair'?'#d7a667': '#dce3db'} strokeWidth="2" strokeDasharray={e.condition==='stair'?'2 5':'4 8'}/></g>; })}
          {Object.entries(Object.groupBy(places.filter(n=>n.buildingId), n=>n.buildingId)).map(([id,ns]) => {const x=ns.reduce((s,n)=>s+position(n).x,0)/ns.length,y=ns.reduce((s,n)=>s+position(n).y,0)/ns.length;return <g key={id} className="map-building" transform={`translate(${x},${y})`}><rect x="-48" y="-27" width="96" height="54" rx="10"/><path d="M-38 -17H38M-38 -10H38" stroke="#dce3ec" strokeWidth="3"/><text y="7">{ns[0].name.split(/ [1-9지]/)[0]}</text></g>;})}
          {points && <><polyline points={points} fill="none" stroke="white" strokeWidth="13" strokeLinejoin="round" strokeLinecap="round"/><polyline points={points} fill="none" stroke={chosenMode.color} strokeWidth="7" strokeLinejoin="round" strokeLinecap="round"/></>}
          {visible.map(n=>{const p=position(n),active=[start,end].includes(n.id);return <g key={n.id} role="button" tabIndex="0" aria-label={n.name} onClick={()=>setSelected(n.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' ')setSelected(n.id);}} className="node-hit" transform={`translate(${p.x},${p.y})`}><title>{n.name}</title><circle r="14" fill="transparent"/><circle r={active?7:4} fill={active?'#3979ef':n.kind==='entrance'?'#fff':'#9eafa0'} stroke={active?'white':'#739281'} strokeWidth="2"/>{active&&<g transform="translate(0,-26)" filter="url(#pin-shadow)"><rect x="-18" y="-21" width="36" height="36" rx="13" fill={n.id===start?'#3478f6':'#142d4c'}/><text className="endpoint-text" y="3">{n.id===start?'A':'B'}</text></g>}</g>;})}
        </svg></div>}
        <div className="floating-map-label"><span>◉</span><div><b>죽전캠퍼스</b><small>{places.length}개 출입구·분기점 연결</small></div></div>
        {!live&&<div className="zoom-control"><button aria-label="확대" onClick={()=>setZoom(z=>Math.min(2,z+.25))}>+</button><button aria-label="축소" onClick={()=>setZoom(z=>Math.max(1,z-.25))}>−</button><button aria-label="지도 초기화" onClick={()=>setZoom(1)}>⌖</button></div>}
        {selected&&<div className="place-card"><button className="close-card" aria-label="장소 닫기" onClick={()=>setSelected(null)}>×</button><span className="eyebrow">{byId[selected].kind==='entrance'?'BUILDING ENTRANCE':'CAMPUS WAYPOINT'}</span><h3>{byId[selected].name}</h3><p>{byId[selected].floor!=null?`${byId[selected].floor}층 · `:''}사용자 제공 좌표</p><div><button onClick={()=>{choose(setStart,selected);setSelected(null);}}>출발지로</button><button onClick={()=>{choose(setEnd,selected);setSelected(null);}}>도착지로</button></div></div>}
        <div className="map-caption">{live?'Kakao Maps':'입력 좌표 기반 개략도 · 건물 도형은 실제 외곽선이 아닙니다'}</div></div>
        <div className="map-bottom"><button className="entrance-toggle" role="switch" aria-checked={showEntrances} onClick={() => { setShowEntrances(v => !v); setSelected(null); }}><span className={`toggle-track ${showEntrances ? 'on' : ''}`}><span /></span><span>출입구 {showEntrances ? '표시' : '숨김'}</span></button><div className="filter-buttons">{[['all','전체 보기'],['entrance','출입구'],['junction','분기점']].map(([id,label])=><button className={filter===id?'selected':''} key={id} onClick={()=>setFilter(id)}>{label}</button>)}</div><span><i className="legend-dot"/> 출입구 <i className="legend-line"/> 연결 보행로</span></div>
        {mapError&&<div className="map-feedback" role="status">{mapError}<button onClick={()=>setMapError('')} aria-label="알림 닫기">×</button></div>}
      </main>
    </div>
    <footer className="page-footer"><b>DKU SafePath</b><span>더 가까운 캠퍼스, 모두를 위한 이동.</span><small>단국대학교 학생 프로젝트 · Prototype</small></footer>
    {about&&<div className="modal-backdrop" onClick={()=>setAbout(false)}><section role="dialog" aria-modal="true" aria-label="서비스 소개" className="about-dialog" onClick={e=>e.stopPropagation()}><button onClick={()=>setAbout(false)} aria-label="닫기">×</button><span className="eyebrow">ABOUT SAFEPATH</span><h2>모두에게 열린 캠퍼스를 위해.</h2><p>DKU SafePath는 학생과 보행약자의 이동을 돕는 캠퍼스 길찾기 프로젝트입니다. 사용자 제공 좌표와 팀이 작성한 연결 정보를 활용합니다.</p><p>현재 화면은 실외·건물 간 연결을 탐색합니다. 실측 시간, 조명 상태, 시설 위치 및 실내 층간 길찾기는 추후 데이터 연동이 필요합니다.</p></section></div>}
    <button className="chat-launch" aria-label="채팅 도우미 열기" onClick={()=>setChat(v=>!v)}>{chat?'×':'✦'}<span>캠퍼스 도우미</span></button>
{chat&&<section className="chat-window" aria-label="캠퍼스 도우미"><header><span>✦ 캠퍼스 도우미<small>Gemini AI · 교내 데이터 기반 안내</small></span><button aria-label="채팅 닫기" onClick={()=>setChat(false)}>×</button></header><div className="messages" aria-live="polite">{messages.map((m,i)=><p key={i} className={m.role}>{m.text}</p>)}{busy&&<p>답변을 준비하고 있어요…</p>}</div><form onSubmit={send}><input aria-label="질문" maxLength={4000} placeholder="예: 정문에서 인문관 2층까지 계단 없이" value={input} onChange={e=>setInput(e.target.value)}/><button disabled={busy||!input.trim()} aria-label="질문 보내기">↑</button></form></section>}
  </div>;
}
