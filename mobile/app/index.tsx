import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  ScrollView,
  StyleSheet,
  Text,
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
import {
  parsePlan,
  crossCheck,
  downloadExcelBase64,
  generateIncomingExcel,
  type PlanItem,
  type CrossCheckResponse,
} from "../src/services/api";

interface PickedFile {
  uri: string;
  name: string;
  isImage: boolean;
}

export default function HomeScreen() {
  const [userName, setUserName] = useState("");
  const [planFiles, setPlanFiles] = useState<PickedFile[]>([]);
  const [erpFile, setErpFile] = useState<PickedFile | null>(null);
  const [loading, setLoading] = useState(false);

  // Step 1: 입고 예정 리스트
  const [planItems, setPlanItems] = useState<PlanItem[] | null>(null);

  // Step 2: 교차검증 결과
  const [result, setResult] = useState<CrossCheckResponse | null>(null);

  const [incomingLoading, setIncomingLoading] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem("user_token").then((token) => {
      if (!token) {
        router.replace("/login");
      } else {
        AsyncStorage.getItem("user_name").then((name) => {
          if (name) setUserName(name);
        });
      }
    });
  }, []);

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
      quality: 0.5,
      maxWidth: 1600,
      maxHeight: 1600,
    });
    if (pickerResult.canceled) return;
    const asset = pickerResult.assets[0];
    const file: PickedFile = { uri: asset.uri, name: asset.fileName || `photo_${Date.now()}.jpg`, isImage: true };
    if (target === "plan") {
      setPlanFiles((prev) => prev.length >= 5 ? prev : [...prev, file]);
    } else setErpFile(file);
  };

  const takePhoto = async (target: "plan" | "erp") => {
    const permResult = await ImagePicker.requestCameraPermissionsAsync();
    if (!permResult.granted) {
      Alert.alert("권한 필요", "카메라 접근 권한이 필요합니다.");
      return;
    }
    const pickerResult = await ImagePicker.launchCameraAsync({ quality: 0.5, maxWidth: 1600, maxHeight: 1600 });
    if (pickerResult.canceled) return;
    const asset = pickerResult.assets[0];
    const file: PickedFile = { uri: asset.uri, name: asset.fileName || `photo_${Date.now()}.jpg`, isImage: true };
    if (target === "plan") {
      setPlanFiles((prev) => prev.length >= 5 ? prev : [...prev, file]);
    } else setErpFile(file);
  };

  const pickDocument = async (target: "plan" | "erp") => {
    try {
      const docResult = await DocumentPicker.getDocumentAsync({
        type: ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel", "text/csv", "image/*"],
        copyToCacheDirectory: true,
      });
      if (docResult.canceled) return;
      const asset = docResult.assets[0];
      const ext = asset.name.toLowerCase().split(".").pop() || "";
      const file = { uri: asset.uri, name: asset.name, isImage: ["jpg", "jpeg", "png", "webp"].includes(ext) };
      if (target === "plan") {
        setPlanFiles((prev) => prev.length >= 5 ? prev : [...prev, file]);
      } else setErpFile(file);
    } catch { Alert.alert("오류", "파일을 선택할 수 없습니다."); }
  };

  const handleImagePick = (target: "plan" | "erp") => {
    Alert.alert("사진 선택", "촬영 또는 갤러리에서 선택하세요.", [
      { text: "카메라 촬영", onPress: () => takePhoto(target) },
      { text: "갤러리 선택", onPress: () => pickImage(target) },
      { text: "취소", style: "cancel" },
    ]);
  };

  // Step 1: 입고 예정 리스트 추출
  const runParsePlan = async () => {
    if (planFiles.length === 0) return;
    setLoading(true);
    setPlanItems(null);
    setResult(null);
    try {
      const response = await parsePlan(
        planFiles.map((f) => f.uri),
        planFiles.map((f) => f.name),
        ""
      );
      setPlanItems(response.items);
    } catch (e: any) {
      Alert.alert("분석 실패", e.message || "서버 연결을 확인하세요.");
    } finally {
      setLoading(false);
    }
  };

  // Step 2: 교차검증
  const runVerification = async () => {
    if (planFiles.length === 0 || !erpFile) return;
    setLoading(true);
    setResult(null);
    try {
      const response = await crossCheck(
        planFiles.map((f) => f.uri),
        planFiles.map((f) => f.name),
        erpFile.uri,
        erpFile.name,
        ""
      );
      setResult(response);
    } catch (e: any) {
      Alert.alert("검증 실패", e.message || "서버 연결을 확인하세요.");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setPlanFiles([]);
    setErpFile(null);
    setPlanItems(null);
    setResult(null);
  };

  return (
    <>
      <Stack.Screen
        options={{
          title: "KG Counter",
          headerRight: () => (
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12, marginRight: 4 }}>
              <TouchableOpacity onPress={() => router.push("/inventory")}>
                <Text style={{ color: "#fff", fontSize: 13, fontWeight: "600" }}>재고</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={handleLogout}>
                <Text style={{ color: "#fff", fontSize: 13 }}>{userName} | 로그아웃</Text>
              </TouchableOpacity>
            </View>
          ),
        }}
      />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* 로고 */}
        <View style={styles.logoHeader}>
          <Image source={require("../assets/kg.jpg")} style={styles.logo} resizeMode="contain" />
        </View>

        {/* ── STEP 1: 생산계획서 첨부 ── */}
        <Text style={styles.stepTitle}>① 생산계획서 첨부</Text>

        {planItems && (
          <TouchableOpacity style={styles.resetBtn} onPress={handleReset}>
            <Text style={styles.resetBtnText}>🔄 새 생산계획서로 다시 시작</Text>
          </TouchableOpacity>
        )}

        {!planItems && (
          <>
            <View style={styles.multiCard}>
              <Text style={styles.multiTitle}>생산계획서 ({planFiles.length}/5)</Text>
              {planFiles.length === 0 && (
                <Text style={styles.multiHint}>이미지 또는 엑셀 파일을 첨부하세요.</Text>
              )}
              {planFiles.map((f, idx) => (
                <View key={idx} style={styles.multiFileRow}>
                  <Text style={styles.multiFileName} numberOfLines={1}>{f.name}</Text>
                  <TouchableOpacity onPress={() => setPlanFiles((prev) => prev.filter((_, i) => i !== idx))}>
                    <Text style={styles.multiRemove}>삭제</Text>
                  </TouchableOpacity>
                </View>
              ))}
              {planFiles.length < 5 && (
                <View style={styles.multiButtons}>
                  <TouchableOpacity style={styles.multiBtn} onPress={() => handleImagePick("plan")}>
                    <Text style={styles.multiBtnText}>촬영/갤러리</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.multiBtn} onPress={() => pickDocument("plan")}>
                    <Text style={styles.multiBtnText}>파일 선택</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>

            <TouchableOpacity
              style={[styles.runButton, (planFiles.length === 0 || loading) && styles.runButtonDisabled]}
              onPress={runParsePlan}
              disabled={planFiles.length === 0 || loading}
            >
              {loading ? <ActivityIndicator color="#fff" /> : (
                <Text style={styles.runButtonText}>📋 입고 예정 리스트 추출</Text>
              )}
            </TouchableOpacity>
          </>
        )}

        {/* 입고 예정 리스트 */}
        {planItems && (
          <View style={styles.resultSection}>
            <Text style={styles.sectionTitle}>📦 입고 예정 품목 ({planItems.length}건)</Text>
            {planItems.filter((i) => i.신규 > 0).map((item, idx) => (
              <View key={idx} style={styles.incomingRow}>
                <Text style={styles.incomingNo}>{idx + 1}</Text>
                <Text style={styles.incomingCode}>{item.색상코드}</Text>
                <Text style={styles.incomingMaker}>{item.제조사}</Text>
                <Text style={styles.incomingQty}>{item.신규}</Text>
                {item.비고 ? <Text style={styles.incomingNote}>{item.비고}</Text> : null}
              </View>
            ))}

            {/* 입고 예정 엑셀 다운로드 */}
            <TouchableOpacity
              style={[styles.incomingBtn, incomingLoading && styles.runButtonDisabled]}
              onPress={async () => {
                setIncomingLoading(true);
                try {
                  const excelB64 = await generateIncomingExcel(planItems);
                  const path = `${FileSystem.cacheDirectory}incoming_${Date.now()}.xlsx`;
                  await FileSystem.writeAsStringAsync(path, excelB64, { encoding: FileSystem.EncodingType.Base64 });
                  if (await Sharing.isAvailableAsync()) {
                    await Sharing.shareAsync(path, {
                      mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      dialogTitle: "입고 예정 품목",
                    });
                  }
                } catch (e: any) { Alert.alert("엑셀 실패", e.message); }
                finally { setIncomingLoading(false); }
              }}
              disabled={incomingLoading}
            >
              {incomingLoading ? <ActivityIndicator color="#fff" /> : (
                <Text style={styles.incomingBtnText}>📥 입고 예정 엑셀 다운로드</Text>
              )}
            </TouchableOpacity>

            {/* ── STEP 2: ERP 첨부 → 교차검증 ── */}
            <View style={styles.divider} />
            <Text style={styles.stepTitle}>② 입고 완료 후 ERP 첨부</Text>

            <FileUploadCard
              title="ERP 입고명세서"
              hint="입고명세 문서/이미지를 첨부하세요."
              icon="document-text"
              fileName={erpFile?.name}
              fileUri={erpFile?.uri}
              isImage={erpFile?.isImage}
              onPickImage={() => handleImagePick("erp")}
              onPickFile={() => pickDocument("erp")}
              onClear={() => setErpFile(null)}
            />

            <TouchableOpacity
              style={[styles.runButton, (!erpFile || loading) && styles.runButtonDisabled]}
              onPress={runVerification}
              disabled={!erpFile || loading}
            >
              {loading ? <ActivityIndicator color="#fff" /> : (
                <Text style={styles.runButtonText}>🔍 교차검증 실행</Text>
              )}
            </TouchableOpacity>
          </View>
        )}

        {/* 교차검증 결과 */}
        {result && (
          <View style={styles.resultSection}>
            <Text style={styles.sectionTitle}>✅ 교차검증 결과</Text>
            <SummaryCards summary={result.summary} />

            {result.summary.reverse_count > 0 && (
              <View style={styles.warningBox}>
                <Text style={styles.warningText}>
                  ⚠️ 확인필요 {result.summary.reverse_count}건: 생산계획서에 없지만 ERP에 입고 기록이 있는 품목입니다. 인식 누락 또는 긴급 입고분일 수 있으니 확인 바랍니다.
                </Text>
              </View>
            )}

            <View style={styles.totalRow}>
              <Text style={styles.totalText}>
                계획: {result.summary.total_plan} | 입고: {result.summary.total_actual} | 차이: {result.summary.total_actual - result.summary.total_plan}
              </Text>
            </View>

            <ResultTable results={result.results} />

            <TouchableOpacity
              style={styles.downloadButton}
              onPress={async () => {
                try {
                  setLoading(true);
                  const excelBase64 = await downloadExcelBase64(
                    planFiles.map((f) => f.uri), planFiles.map((f) => f.name),
                    erpFile!.uri, erpFile!.name, ""
                  );
                  const path = `${FileSystem.cacheDirectory}report_${Date.now()}.xlsx`;
                  await FileSystem.writeAsStringAsync(path, excelBase64, { encoding: FileSystem.EncodingType.Base64 });
                  if (await Sharing.isAvailableAsync()) {
                    await Sharing.shareAsync(path, {
                      mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      dialogTitle: "검증 리포트",
                    });
                  }
                } catch (e: any) { Alert.alert("다운로드 실패", e.message); }
                finally { setLoading(false); }
              }}
              disabled={loading}
            >
              <Text style={styles.downloadButtonText}>📥 검증 결과 엑셀 다운로드</Text>
            </TouchableOpacity>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  content: { padding: 16 },
  logoHeader: { alignItems: "center", paddingVertical: 12, marginBottom: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  logo: { width: 160, height: 60 },
  stepTitle: { fontSize: 17, fontWeight: "700", color: COLORS.textPrimary, marginBottom: 8, marginTop: 4 },
  multiCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 16, marginBottom: 12, elevation: 2 },
  multiTitle: { fontSize: 16, fontWeight: "700", color: COLORS.textPrimary, marginBottom: 4 },
  multiHint: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 10 },
  multiFileRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  multiFileName: { flex: 1, fontSize: 13, color: COLORS.textPrimary },
  multiRemove: { fontSize: 13, color: COLORS.error, fontWeight: "600", marginLeft: 12 },
  multiButtons: { flexDirection: "row", gap: 12, marginTop: 10 },
  multiBtn: { flex: 1, alignItems: "center", paddingVertical: 14, borderWidth: 2, borderColor: COLORS.border, borderStyle: "dashed", borderRadius: 10 },
  multiBtnText: { fontSize: 13, color: COLORS.primary, fontWeight: "600" },
  runButton: { backgroundColor: COLORS.primary, paddingVertical: 16, borderRadius: 12, alignItems: "center", marginVertical: 8, elevation: 3 },
  runButtonDisabled: { backgroundColor: "#aaa", elevation: 0 },
  runButtonText: { color: "#fff", fontSize: 18, fontWeight: "700" },
  resetBtn: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border, paddingVertical: 10, borderRadius: 8, alignItems: "center", marginBottom: 12 },
  resetBtnText: { fontSize: 14, color: COLORS.textSecondary, fontWeight: "600" },
  resultSection: { marginTop: 8 },
  sectionTitle: { fontSize: 18, fontWeight: "700", color: COLORS.textPrimary, marginBottom: 12 },
  divider: { height: 1, backgroundColor: COLORS.border, marginVertical: 16 },
  incomingRow: { flexDirection: "row", alignItems: "center", paddingVertical: 8, paddingHorizontal: 12, backgroundColor: COLORS.surface, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  incomingNo: { width: 30, fontSize: 12, color: COLORS.textSecondary, textAlign: "center" },
  incomingCode: { flex: 2, fontSize: 13, fontWeight: "600", color: COLORS.textPrimary },
  incomingMaker: { flex: 1, fontSize: 12, color: COLORS.textSecondary, textAlign: "center" },
  incomingQty: { width: 40, fontSize: 14, fontWeight: "700", color: COLORS.primary, textAlign: "center" },
  incomingNote: { width: 50, fontSize: 11, color: COLORS.textSecondary, textAlign: "center" },
  incomingBtn: { backgroundColor: COLORS.warning, paddingVertical: 14, borderRadius: 12, alignItems: "center", marginTop: 12, marginBottom: 4 },
  incomingBtnText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  warningBox: { backgroundColor: "#FFF3CD", borderRadius: 8, padding: 12, marginBottom: 12, borderLeftWidth: 4, borderLeftColor: "#FFC107" },
  warningText: { fontSize: 12, color: "#856404" },
  totalRow: { backgroundColor: COLORS.surface, padding: 12, borderRadius: 8, marginBottom: 12, alignItems: "center" },
  totalText: { fontSize: 14, fontWeight: "600", color: COLORS.textPrimary },
  downloadButton: { backgroundColor: COLORS.success, paddingVertical: 14, borderRadius: 12, alignItems: "center", marginTop: 16 },
  downloadButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
