const { withProjectBuildGradle } = require("@expo/config-plugins");

/**
 * jitpack.io 타임아웃으로 인한 bouncycastle 의존성 해석 실패 방지.
 * allprojects 레벨에서 정확한 버전을 강제하여 모든 서브모듈에 적용.
 */
module.exports = function withBouncyCastleFix(config) {
  return withProjectBuildGradle(config, (config) => {
    if (!config.modResults.contents.includes("bcprov-jdk15to18")) {
      // allprojects 블록 안에 configurations.all 추가
      config.modResults.contents = config.modResults.contents.replace(
        /allprojects\s*\{/,
        `allprojects {
    configurations.all {
        resolutionStrategy {
            force 'org.bouncycastle:bcprov-jdk15to18:1.81'
            force 'org.bouncycastle:bcutil-jdk15to18:1.81'
        }
    }`
      );
    }
    return config;
  });
};
