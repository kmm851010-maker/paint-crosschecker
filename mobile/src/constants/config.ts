// 백엔드 서버 주소 (개발 시 로컬 IP로 변경)
// Android 에뮬레이터: 10.0.2.2, iOS 시뮬레이터: localhost
// 실제 기기: 같은 Wi-Fi 네트워크의 PC IP 주소
export const API_BASE_URL = "http://192.168.45.48:8000";

export const COLORS = {
  primary: "#4B2D8E",      // KG스틸 보라
  primaryDark: "#3A2270",
  success: "#2e7d32",
  successLight: "#c6efce",
  warning: "#ed6c02",
  warningLight: "#fce4d6",
  error: "#d32f2f",
  errorLight: "#ffc7ce",
  missingLight: "#ff9999",
  background: "#f5f5f5",
  surface: "#ffffff",
  textPrimary: "#212121",
  textSecondary: "#757575",
  border: "#e0e0e0",
} as const;

export const STATUS_COLORS: Record<string, string> = {
  일치: COLORS.successLight,
  초과: COLORS.warningLight,
  부족: COLORS.errorLight,
  미입고: COLORS.missingLight,
};

export const STATUS_TEXT_COLORS: Record<string, string> = {
  일치: COLORS.success,
  초과: COLORS.warning,
  부족: COLORS.error,
  미입고: COLORS.error,
};
