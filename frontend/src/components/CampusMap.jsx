import { hasKakaoMapKey } from "../services/mapService";
import KakaoCampusMap from "./KakaoCampusMap";
import MockCampusMap from "./MockCampusMap";

export default function CampusMap(props) {
  return hasKakaoMapKey() ? (
    <KakaoCampusMap {...props} />
  ) : (
    <MockCampusMap {...props} />
  );
}
