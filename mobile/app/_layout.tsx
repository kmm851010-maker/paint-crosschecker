import { useEffect, useState } from "react";
import { Stack, router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import AsyncStorage from "@react-native-async-storage/async-storage";

export default function RootLayout() {
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem("user_token").then((token) => {
      if (!token) {
        router.replace("/login");
      }
      setChecked(true);
    });
  }, []);

  if (!checked) return null;

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#C8102E" },
          headerTintColor: "#fff",
          headerTitleStyle: { fontWeight: "700" },
        }}
      />
    </>
  );
}
