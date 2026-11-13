import { types } from "../data/facilities";
export default function FacilityMarker({ facility, selected, onClick }) {
  let t = types.find((x) => x.id === facility.type);
  return (
    <button
      className={"marker " + (selected ? "on" : "")}
      style={{ left: facility.x + "%", top: facility.y + "%" }}
      onClick={() => onClick(facility)}
      title={facility.name}
    >
      {t.icon}
    </button>
  );
}
