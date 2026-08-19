import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Stack, router, useFocusEffect } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import AsyncStorage from "@react-native-async-storage/async-storage";

import FileUploadCard from "../src/components/FileUploadCard";
import SummaryCards from "../src/components/SummaryCards";
import ResultTable from "../src/components/ResultTable";
import { COLORS } from "../src/constants/config";
import { crossCheck, downloadExcelBase64, type CrossCheckResponse } from "../src/services/api";

interface PickedFile {
  uri: string;
  name: string;
  isImage: boolean;
}

interface Slot {
  id: string;
  name: string;
  leftLabel: string;
  rightLabel: string;
}

export default function HomeScreen() {
  const [userName, setUserName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [planFile, setPlanFile] = useState<PickedFile | null>(null);
  const [erpFile, setErpFile] = useState<PickedFile | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CrossCheckResponse | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [activeSlot, setActiveSlot] = useState<Slot | null>(null);

  useEffect(() => {
    AsyncStorage.getItem("user_token").then((token) => {
      if (!token) {
        router.replace("/login");
      } else {
        AsyncStorage.getItem("user_name").then((name) => {
          if (name) setUserName(name);
        });
        loadSlots();
      }
    });
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadSlots();
    }, [])
  );

  const loadSlots = async () => {
    const data = await AsyncStorage.getItem("kg_counter_slots");
    if (data) {
      const parsed = JSON.parse(data) as Slot[];
      setSlots(parsed);
      if (parsed.length > 0) {
        setActiveSlot((prev) => {
          if (prev && parsed.find((s) => s.id === prev.id)) return prev;
          return parsed[0];
        });
      }
    }
  };

  const handleLogout = () => {
    Alert.alert("로그아웃", "로그아웃 하시겠습니까?", [
      { text: "취소", style: "cancel" },
      {
        text: "로그아웃",
        style: "destructive",
        onPress: async () => {
          await AsyncStorage.multiRemove(["user_token", "user_name", "employee_id"]);
          router.replace("/login");
        },
      },
    ]);
  };

  const pickImage = async (target: "plan" | "erp") => {
    const permResult = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permResult.granted) {
      Alert.alert("권한 필요", "갤러리 접근 권한이 필요합니다.");
      return;
    }

    const pickerResult = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.9,
    });

    if (pickerResult.canceled) return;

    const asset = pickerResult.assets[0];
    const fileName = asset.fileName || `photo_${Date.now()}.jpg`;
    const file: PickedFile = { uri: asset.uri, name: fileName, isImage: true };

    if (target === "plan") setPlanFile(file);
    else setErpFile(file);
  };

  const takePhoto = async (target: "plan" | "erp") => {
    const permResult = await ImagePicker.requestCameraPermissionsAsync();
    if (!permResult.granted) {
      Alert.alert("권한 필요", "카메라 접근 권한이 필요합니다.");
      return;
    }

    const pickerResult = await ImagePicker.launchCameraAsync({
      quality: 0.9,
    });

    if (pickerResult.canceled) return;

    const asset = pickerResult.assets[0];
    const fileName = asset.fileName || `photo_${Date.now()}.jpg`;
    const file: PickedFile = { uri: asset.uri, name: fileName, isImage: true };

    if (target === "plan") setPlanFile(file);
    else setErpFile(file);
  };

  const pickDocument = async (target: "plan" | "erp") => {
    try {
      const docResult = await DocumentPicker.getDocumentAsync({
        type: [
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "application/vnd.ms-excel",
          "text/csv",
          "image/*",
        ],
        copyToCacheDirectory: true,
      });

      if (docResult.canceled) return;

      const asset = docResult.assets[0];
      const ext = asset.name.toLowerCase().split(".").pop() || "";
      const isImage = ["jpg", "jpeg", "png", "webp"].includes(ext);
      const file = { uri: asset.uri, name: asset.name, isImage };

      if (target === "plan") setPlanFile(file);
      else setErpFile(file);
    } catch (e) {
      Alert.alert("오류", "파일을 선택할 수 없습니다.");
    }
  };

  const handleImagePick = (target: "plan" | "erp") => {
    Alert.alert("사진 선택", "촬영 또는 갤러리에서 선택하세요.", [
      { text: "카메라 촬영", onPress: () => takePhoto(target) },
      { text: "갤러리 선택", onPress: () => pickImage(target) },
      { text: "취소", style: "cancel" },
    ]);
  };

  const runVerification = async () => {
    if (!planFile || !erpFile) {
      Alert.alert("파일 필요", "생산계획서와 ERP 명세서를 모두 업로드하세요.");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await crossCheck(
        planFile.uri,
        planFile.name,
        erpFile.uri,
        erpFile.name,
        apiKey
      );
      setResult(response);
    } catch (e: any) {
      Alert.alert("검증 실패", e.message || "서버 연결을 확인하세요.");
    } finally {
      setLoading(false);
    }
  };

  const handleExcelDownload = async () => {
    if (!planFile || !erpFile) return;

    try {
      setLoading(true);

      const excelBase64 = await downloadExcelBase64(
        planFile.uri,
        planFile.name,
        erpFile.uri,
        erpFile.name,
        apiKey
      );

      const downloadPath = `${FileSystem.cacheDirectory}report_${Date.now()}.xlsx`;
      await FileSystem.writeAsStringAsync(downloadPath, excelBase64, {
        encoding: FileSystem.EncodingType.Base64,
      });

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(downloadPath, {
          mimeType:
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          dialogTitle: "검증 리포트 공유",
        });
      } else {
        Alert.alert("완료", "파일이 저장되었습니다.");
      }
    } catch (e: any) {
      Alert.alert("다운로드 실패", e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Stack.Screen
        options={{
          title: "KG Counter",
          headerRight: () => (
            <TouchableOpacity onPress={handleLogout} style={{ marginRight: 4 }}>
              <Text style={{ color: "#fff", fontSize: 13 }}>
                {userName} | 로그아웃
              </Text>
            </TouchableOpacity>
          ),
        }}
      />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* KG스틸 로고 */}
        <View style={styles.logoHeader}>
          <Image source={require("../assets/kg.jpg")} style={styles.logo} resizeMode="contain" />
        </View>

        {/* 슬롯 선택 */}
        {slots.length > 0 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.slotBar}>
            {slots.map((slot) => (
              <TouchableOpacity
                key={slot.id}
                style={[
                  styles.slotChip,
                  activeSlot?.id === slot.id && styles.slotChipActive,
                ]}
                onPress={() => {
                  setActiveSlot(slot);
                  setPlanFile(null);
                  setErpFile(null);
                  setResult(null);
                }}
              >
                <Text
                  style={[
                    styles.slotChipText,
                    activeSlot?.id === slot.id && styles.slotChipTextActive,
                  ]}
                >
                  {slot.name}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}

        {/* 설정 버튼 */}
        <TouchableOpacity
          style={styles.settingsButton}
          onPress={() => router.push("/settings")}
        >
          <Text style={styles.settingsButtonText}>슬롯 관리</Text>
        </TouchableOpacity>

        {/* API Key */}
        <TouchableOpacity
          style={styles.apiKeyToggle}
          onPress={() => setShowApiKey(!showApiKey)}
        >
          <Text style={styles.apiKeyToggleText}>
            {showApiKey ? "▼ API Key 설정" : "▶ API Key 설정"}
          </Text>
        </TouchableOpacity>

        {showApiKey && (
          <TextInput
            style={styles.input}
            placeholder=""
            value={apiKey}
            onChangeText={setApiKey}
            secureTextEntry
            autoCapitalize="none"
          />
        )}

        {/* Upload Cards */}
        <FileUploadCard
          title={activeSlot?.leftLabel || "좌측 문서"}
          icon="camera"
          fileName={planFile?.name}
          fileUri={planFile?.uri}
          isImage={planFile?.isImage}
          onPickImage={() => handleImagePick("plan")}
          onPickFile={() => pickDocument("plan")}
          onClear={() => setPlanFile(null)}
        />

        <FileUploadCard
          title={activeSlot?.rightLabel || "우측 문서"}
          icon="document-text"
          fileName={erpFile?.name}
          fileUri={erpFile?.uri}
          isImage={erpFile?.isImage}
          onPickImage={() => handleImagePick("erp")}
          onPickFile={() => pickDocument("erp")}
          onClear={() => setErpFile(null)}
        />

        {/* Run Button */}
        <TouchableOpacity
          style={[
            styles.runButton,
            (!planFile || !erpFile || loading) && styles.runButtonDisabled,
          ]}
          onPress={runVerification}
          disabled={!planFile || !erpFile || loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.runButtonText}>검증 실행</Text>
          )}
        </TouchableOpacity>

        {/* Results */}
        {result && (
          <View style={styles.resultSection}>
            <Text style={styles.sectionTitle}>교차검증 결과</Text>

            <SummaryCards summary={result.summary} />

            <View style={styles.totalRow}>
              <Text style={styles.totalText}>
                계획: {result.summary.total_plan} | 입고:{" "}
                {result.summary.total_actual} | 차이:{" "}
                {result.summary.total_actual - result.summary.total_plan}
              </Text>
            </View>

            <ResultTable results={result.results} />

            {/* Excel Download */}
            <TouchableOpacity
              style={styles.downloadButton}
              onPress={handleExcelDownload}
              disabled={loading}
            >
              <Text style={styles.downloadButtonText}>
                결과 엑셀 다운로드
              </Text>
            </TouchableOpacity>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  content: {
    padding: 16,
  },
  logoHeader: {
    alignItems: "center",
    paddingVertical: 12,
    marginBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  logo: {
    width: 160,
    height: 60,
  },
  slotBar: {
    marginBottom: 8,
    maxHeight: 44,
  },
  slotChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginRight: 8,
  },
  slotChipActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  slotChipText: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.textPrimary,
  },
  slotChipTextActive: {
    color: "#fff",
  },
  settingsButton: {
    alignSelf: "flex-end",
    paddingVertical: 6,
    paddingHorizontal: 12,
    marginBottom: 8,
  },
  settingsButtonText: {
    fontSize: 13,
    color: COLORS.primary,
    fontWeight: "600",
  },
  apiKeyToggle: {
    marginBottom: 8,
  },
  apiKeyToggleText: {
    fontSize: 13,
    color: COLORS.textSecondary,
  },
  input: {
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 14,
  },
  runButton: {
    backgroundColor: COLORS.primary,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
    marginVertical: 8,
    elevation: 3,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
  runButtonDisabled: {
    backgroundColor: "#aaa",
    elevation: 0,
    shadowOpacity: 0,
  },
  runButtonText: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "700",
  },
  resultSection: {
    marginTop: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: COLORS.textPrimary,
    marginBottom: 12,
  },
  totalRow: {
    backgroundColor: COLORS.surface,
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
    alignItems: "center",
  },
  totalText: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.textPrimary,
  },
  downloadButton: {
    backgroundColor: COLORS.success,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 16,
  },
  downloadButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
  },
});
