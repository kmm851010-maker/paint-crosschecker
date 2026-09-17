export const AUTH_KEY = "kg_token";
export const USER_KEY = "kg_user";

export interface KGUser {
  token: string;
  name: string;
  employee_id: string;
  role?: string;
}

export function saveAuth(user: KGUser) {
  localStorage.setItem(AUTH_KEY, user.token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getAuth(): KGUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAdmin(): boolean {
  const u = getAuth();
  return u?.employee_id === "admin" || u?.employee_id === "kg";
}
