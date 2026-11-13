import { types } from "../data/facilities";
export default function FacilityFilter({ value, onChange }) {
  return (
    <div className="filters" id="facilities">
      {types.map((t) => (
        <button
          className={value === t.id ? "on" : ""}
          onClick={() => onChange(t.id)}
          key={t.id}
        >
          <span>{t.icon}</span>
          {t.label}
        </button>
      ))}
    </div>
  );
}
