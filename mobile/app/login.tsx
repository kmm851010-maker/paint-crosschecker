import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { router, Stack } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { COLORS } from "../src/constants/config";

export default function LoginScreen() {
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!employeeId.trim() || !password.trim()) {
      Alert.alert("입력 오류", "사번과 비밀번호를 모두 입력하세요.");
      return;
    }

    setLoading(true);

    try {
      // 사내 인증 API 연동 시 여기를 수정하세요
      // 현재는 간단한 로컬 인증 (사번 입력만으로 통과)
      const { API_BASE_URL } = require("../src/constants/config");
      const response = await fetch(`${API_BASE_URL}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: employeeId.trim(),
          password: password.trim(),
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "인증 실패" }));
        throw new Error(err.detail || "로그인 실패");
      }

      const data = await response.json();

      // 로그인 정보 저장
      await AsyncStorage.setItem("user_token", data.token || "authenticated");
      await AsyncStorage.setItem("user_name", data.name || employeeId);
      await AsyncStorage.setItem("employee_id", employeeId);

      router.replace("/");
    } catch (e: any) {
      // 서버 연결 실패 시 오프라인 모드로 진입 가능
      if (e.message?.includes("Network") || e.message?.includes("fetch")) {
        Alert.alert(
          "서버 연결 불가",
          "서버에 연결할 수 없습니다.\n오프라인 모드로 진입하시겠습니까?",
          [
            { text: "취소", style: "cancel" },
            {
              text: "오프라인 진입",
              onPress: async () => {
                await AsyncStorage.setItem("user_token", "offline");
                await AsyncStorage.setItem("user_name", employeeId);
                await AsyncStorage.setItem("employee_id", employeeId);
                router.replace("/");
              },
            },
          ]
        );
      } else {
        Alert.alert("로그인 실패", e.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Stack.Screen options={{ headerShown: false }} />
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.inner}>
          {/* 로고 영역 */}
          <View style={styles.logoSection}>
            <View style={styles.logoBox}>
              {/* KG스틸 로고 파일이 있으면 아래 Image 주석 해제 */}
              {/* <Image source={require("../assets/kg-logo.png")} style={styles.logoImage} resizeMode="contain" /> */}
              <Text style={styles.logoText}>KG스틸</Text>
            </View>
            <Text style={styles.appTitle}>페인트 입고 검증 시스템</Text>
            <Text style={styles.appSubtitle}>Paint Incoming Verification</Text>
          </View>

          {/* 로그인 폼 */}
          <View style={styles.formSection}>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>사번</Text>
              <TextInput
                style={styles.input}
                placeholder="사번을 입력하세요"
                placeholderTextColor="#999"
                value={employeeId}
                onChangeText={setEmployeeId}
                autoCapitalize="none"
                returnKeyType="next"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>비밀번호</Text>
              <TextInput
                style={styles.input}
                placeholder="비밀번호를 입력하세요"
                placeholderTextColor="#999"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                returnKeyType="done"
                onSubmitEditing={handleLogin}
              />
            </View>

            <TouchableOpacity
              style={[styles.loginButton, loading && styles.loginButtonDisabled]}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.loginButtonText}>로그인</Text>
              )}
            </TouchableOpacity>
          </View>

          {/* 하단 */}
          <Text style={styles.footer}>KG Steel Co., Ltd.</Text>
        </View>
      </KeyboardAvoidingView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  inner: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  logoSection: {
    alignItems: "center",
    marginBottom: 40,
  },
  logoBox: {
    width: 100,
    height: 100,
    borderRadius: 20,
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
    elevation: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
  },
  logoImage: {
    width: 70,
    height: 70,
  },
  logoText: {
    fontSize: 24,
    fontWeight: "900",
    color: "#fff",
    letterSpacing: 2,
  },
  appTitle: {
    fontSize: 22,
    fontWeight: "700",
    color: COLORS.textPrimary,
    marginBottom: 4,
  },
  appSubtitle: {
    fontSize: 13,
    color: COLORS.textSecondary,
    letterSpacing: 1,
  },
  formSection: {
    backgroundColor: COLORS.surface,
    borderRadius: 16,
    padding: 24,
    elevation: 3,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.textPrimary,
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: COLORS.textPrimary,
    backgroundColor: COLORS.background,
  },
  loginButton: {
    backgroundColor: COLORS.primary,
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 8,
  },
  loginButtonDisabled: {
    opacity: 0.6,
  },
  loginButtonText: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "700",
  },
  footer: {
    textAlign: "center",
    color: COLORS.textSecondary,
    fontSize: 12,
    marginTop: 40,
    letterSpacing: 1,
  },
});
