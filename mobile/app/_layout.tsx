import { useEffect, useState } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import AsyncStorage from "@react-native-async-storage/async-storage";

export default function RootLayout() {
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    AsyncStorage.getItem("user_token")
      .then((token) => setIsLoggedIn(!!token))
      .catch(() => setIsLoggedIn(false));
  }, []);

  useEffect(() => {
    if (isLoggedIn === null) return;

    const onLoginPage = segments[0] === "login";

    if (!isLoggedIn && !onLoginPage) {
      router.replace("/login");
    } else if (isLoggedIn && onLoginPage) {
      router.replace("/");
    }
  }, [isLoggedIn, segments]);

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#4B2D8E" },
          headerTintColor: "#fff",
          headerTitleStyle: { fontWeight: "700" },
        }}
      />
    </>
  );
}
