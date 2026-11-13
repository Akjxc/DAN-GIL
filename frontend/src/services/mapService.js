const SDK_ID = "kakao-map-sdk";
let sdkPromise;

export const DKU_CAMPUS_BOUNDS = {
  north: 37.3265,
  south: 37.316,
  west: 127.1225,
  east: 127.133,
};

export function hasKakaoMapKey() {
  return Boolean(import.meta.env.VITE_KAKAO_MAP_KEY);
}

export function loadKakaoMapSdk() {
  if (window.kakao?.maps) return Promise.resolve(window.kakao.maps);
  if (sdkPromise) return sdkPromise;

  const appKey = import.meta.env.VITE_KAKAO_MAP_KEY;
  if (!appKey)
    return Promise.reject(new Error("카카오맵 JavaScript 키가 없습니다."));

  sdkPromise = new Promise((resolve, reject) => {
    const existing = document.getElementById(SDK_ID);
    if (existing) {
      existing.addEventListener("load", () => {
        window.kakao.maps.load(() => resolve(window.kakao.maps));
      });
      existing.addEventListener("error", reject);
      return;
    }

    const script = document.createElement("script");
    script.id = SDK_ID;
    script.async = true;
    script.src =
      "https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey=" +
      encodeURIComponent(appKey);
    script.onload = () => {
      window.kakao.maps.load(() => resolve(window.kakao.maps));
    };
    script.onerror = () =>
      reject(new Error("카카오맵 SDK를 불러오지 못했습니다."));
    document.head.appendChild(script);
  });

  return sdkPromise;
}

// 현재 x/y는 조감도 상대 좌표입니다. 백엔드가 실제 위경도를 제공하면 제거합니다.
export function mockPositionToLatLng(maps, { x, y }) {
  const latitude =
    DKU_CAMPUS_BOUNDS.north -
    (y / 100) * (DKU_CAMPUS_BOUNDS.north - DKU_CAMPUS_BOUNDS.south);
  const longitude =
    DKU_CAMPUS_BOUNDS.west +
    (x / 100) * (DKU_CAMPUS_BOUNDS.east - DKU_CAMPUS_BOUNDS.west);
  return new maps.LatLng(latitude, longitude);
}
