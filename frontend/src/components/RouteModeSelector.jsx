import { modes } from "../algorithms/routeCalculator";
export default function RouteModeSelector({ value, onChange }) {
  return (
    <div className="modes">
      {Object.entries(modes).map(([id, m]) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={value === id ? "on" : ""}
          style={{ "--c": m.color }}
        >
          <span>{m.icon}</span>
          <div>
            <b>{m.label}</b>
            <small>{m.desc}</small>
          </div>
          <i />
        </button>
      ))}
    </div>
  );
}
