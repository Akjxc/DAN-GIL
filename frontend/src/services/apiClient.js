export function buildApiUrl(baseUrl, path) {
  const base = baseUrl.trim();
  if (!base) return path;
  let url;
  try {
    url = new URL(base);
  } catch {
    throw new Error('VITE_API_BASE_URL에 백엔드 HTTPS 주소를 입력해 주세요.');
  }
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('VITE_API_BASE_URL에는 /api 없이 백엔드 HTTPS 주소만 입력해 주세요.');
  }
  return `${url.origin}${path}`;
}

export function apiUrl(path) {
  return buildApiUrl(import.meta.env?.VITE_API_BASE_URL ?? '', path);
}
