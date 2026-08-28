const { withAppBuildGradle } = require("@expo/config-plugins");

/**
 * jitpack.io 타임아웃으로 인한 bouncycastle 의존성 해석 실패 방지.
 * 정확한 버전을 강제하여 maven-metadata.xml 조회 불필요하게 만듦.
 */
module.exports = function withBouncyCastleFix(config) {
  return withAppBuildGradle(config, (config) => {
    if (!config.modResults.contents.includes("bcprov-jdk15to18")) {
      config.modResults.contents = config.modResults.contents.replace(
        /^android\s*\{/m,
        `configurations.all {
    resolutionStrategy {
        force 'org.bouncycastle:bcprov-jdk15to18:1.81'
        force 'org.bouncycastle:bcutil-jdk15to18:1.81'
    }
}

android {`
      );
    }
    return config;
  });
};
