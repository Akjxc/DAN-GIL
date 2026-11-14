import { defineConfig, loadEnv } from "vite";
import { buildApiUrl } from './src/services/apiClient.js';

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  if (command === 'build') {
    if (!env.VITE_API_BASE_URL?.trim()) {
      throw new Error('VITE_API_BASE_URL에 배포된 백엔드 HTTPS 주소를 설정해 주세요.');
    }
    buildApiUrl(env.VITE_API_BASE_URL, '/api/health');
  }
  return {
    server: {
      proxy: {
        "/api": "http://127.0.0.1:8000",
      },
    },
  };
});
