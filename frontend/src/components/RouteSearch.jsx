import RouteModeSelector from "./RouteModeSelector";
import RouteResult from "./RouteResult";
export default function RouteSearch(p) {
  let { places, start, end, setStart, setEnd, mode, setMode, onSearch, route } =
      p,
    names = Object.fromEntries(places.map((x) => [x.id, x.name]));
  return (
    <aside className="search" id="route">
      <div className="title">
        <div>
          <small>SMART CAMPUS NAVIGATION</small>
          <h1>어디로 이동할까요?</h1>
        </div>
        <span>⌖</span>
      </div>
      <div className="inputs">
        <label>
          <i />
          출발지
          <select value={start} onChange={(e) => setStart(e.target.value)}>
            <option value="">장소 선택</option>
            {places.map((x) => (
              <option value={x.id} key={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={() => {
            setStart(end);
            setEnd(start);
          }}
        >
          ⇅
        </button>
        <label>
          <i />
          도착지
          <select value={end} onChange={(e) => setEnd(e.target.value)}>
            <option value="">장소 선택</option>
            {places.map((x) => (
              <option value={x.id} key={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <h4>길찾기 모드</h4>
      <RouteModeSelector value={mode} onChange={setMode} />
      <button
        className="go"
        disabled={!start || !end || start === end}
        onClick={onSearch}
      >
        경로 검색 <span>→</span>
      </button>
      <RouteResult route={route} mode={mode} names={names} />
    </aside>
  );
}
