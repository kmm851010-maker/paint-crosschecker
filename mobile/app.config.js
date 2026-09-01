const base = require("./app.json");
const IS_DEV = process.env.APP_VARIANT === "development";

module.exports = {
  ...base,
  expo: {
    ...base.expo,
    newArchEnabled: false,
    name: IS_DEV ? "KG OPS (Dev)" : base.expo.name,
    android: {
      ...base.expo.android,
      package: IS_DEV
        ? "com.kgsteel.paintchecker.dev"
        : base.expo.android.package,
    },
  },
};
