import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Stack } from "expo-router";

export default function HomeScreen() {
  return (
    <>
      <Stack.Screen options={{ title: "KG스틸 페인트 검증" }} />
      <View style={styles.container}>
        <Text style={styles.title}>KG스틸</Text>
        <Text style={styles.sub}>페인트 입고 검증 시스템</Text>
        <Text style={styles.ok}>앱 연결 성공!</Text>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#f5f5f5" },
  title: { fontSize: 32, fontWeight: "900", color: "#4B2D8E" },
  sub: { fontSize: 16, color: "#555", marginTop: 8 },
  ok: { fontSize: 20, color: "#2e7d32", marginTop: 30, fontWeight: "700" },
});
