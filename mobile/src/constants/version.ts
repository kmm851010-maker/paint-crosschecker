import Constants from "expo-constants";
import * as Updates from "expo-updates";

// 예: "v1.0.0 · 01a159" (OTA 적용됨) / "v1.0.0 · 기본" (설치 당시 번들)
// 어떤 오류가 나도 앱 동작에 영향이 없도록 빈 문자열로 폴백한다.
export const VERSION_LABEL: string = (() => {
  try {
    const version = Constants.expoConfig?.version ?? "?";
    const id = Updates.updateId ? Updates.updateId.slice(0, 6) : "기본";
    return `v${version} · ${id}`;
  } catch {
    return "";
  }
})();
