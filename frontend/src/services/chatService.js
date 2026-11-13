import { notices } from "../data/notices";
export async function sendChatMessage(m) {
  await new Promise((r) => setTimeout(r, 400));
  let q = m.replace(/\s/g, "");
  if (q.includes("편의점"))
    return "시연 지도에서는 혜당관 인근에 Mock 편의점을 표시해요. 실제 매장 위치와 운영 여부는 학교 공식 안내를 확인해 주세요.";
  if (q.includes("주차"))
    return "캠퍼스 동측 주차빌딩 위치에 시연용 마커가 있어요. 시설 필터에서 주차장을 선택해 보세요.";
  if (q.includes("공학관"))
    return "도착지를 공학관으로 설정하면 선택한 모드에 맞춰 Mock 경로를 계산해요.";
  if (q.includes("공지")) return notices.join(" ");
  if (q.includes("계단") || q.includes("휠체어"))
    return "간선에 계단·경사로 정보가 분리되어 있어요. 최소 보행 모드에서 엘리베이터와 가상 포탈 경로를 확인해 보세요.";
  return "저는 미리 작성된 Mock 응답으로 동작해요. 길찾기, 시설, 접근성 경로를 물어보세요.";
}
