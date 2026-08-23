import { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { router } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";

// 앱 진입점: 로그인 확인 후 재고 화면으로 이동
export default function Index() {
  useEffect(() => {
    AsyncStorage.getItem("user_token").then((token) => {
      if (!token) {
        router.replace("/login");
      } else {
        router.replace("/inventory");
      }
    });
  }, []);

  return (
    <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#4B2D8E" }}>
      <ActivityIndicator size="large" color="#fff" />
    </View>
  );
}
