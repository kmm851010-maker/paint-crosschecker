import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";

const AUTH_KEYS = ["user_token", "user_name", "employee_id"];

/**
 * fetch 래퍼.
 * - 저장된 토큰을 X-Auth-Token 헤더로 전송
 * - 서버가 X-Refresh-Token 을 내려주면 저장 (사용할 때마다 만료 24시간 연장)
 * - 서버가 401(AUTH_REQUIRED)을 주면 로그인 정보를 지우고 로그인 화면으로 이동
 * 토큰 처리 중 어떤 오류가 나도 원래 요청 결과에는 영향을 주지 않는다.
 */
export async function authFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...((init.headers as Record<string, string>) ?? {}) };
  try {
    const token = await AsyncStorage.getItem("user_token");
    if (token && token !== "offline") headers["X-Auth-Token"] = token;
  } catch {}

  const res = await fetch(input, { ...init, headers });

  try {
    const fresh = res.headers.get("x-refresh-token");
    if (fresh) await AsyncStorage.setItem("user_token", fresh);
    if (res.status === 401) {
      const body = await res.clone().json().catch(() => null);
      if (body?.code === "AUTH_REQUIRED") {
        await AsyncStorage.multiRemove(AUTH_KEYS);
        router.replace("/login");
      }
    }
  } catch {}

  return res;
}
