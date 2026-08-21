import React, { useState, useRef, useEffect } from "react";
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Stack } from "expo-router";
import { CameraView, useCameraPermissions } from "expo-camera";

import { COLORS } from "../src/constants/config";
import { parseBarcodeText, registerDrums, getSectorInventory, type DrumItem } from "../src/services/api";

// 스캔 박스 영역 (화면 중앙 기준)
const SCREEN = Dimensions.get("window");
const BOX_W = 340;
const BOX_H = 130;
const BOX_LEFT = (SCREEN.width - BOX_W) / 2;
const BOX_TOP = (SCREEN.height - BOX_H) / 2;
const BOX_RIGHT = BOX_LEFT + BOX_W;
const BOX_BOTTOM = BOX_TOP + BOX_H;

const SECTORS = [
  "신나자리", "0~3번자리", "4~6번자리", "7A~C자리", "7D~Z자리",
  "8번자리", "9번자리", "반품자리", "CW2", "CP5", "창고뒤",
];
const CHECKOUT = "라인입고";

type Mode = "idle" | "scanning" | "sectorPick" | "status";

export default function InventoryScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [mode, setMode] = useState<Mode>("idle");

  // 화면 진입 시 자동으로 카메라 권한 요청
  useEffect(() => {
    if (permission && !permission.granted && !permission.canAskAgain) return;
    if (!permission?.granted) {
      requestPermission();
    }
  }, [permission]);
  const [batch, setBatch] = useState<DrumItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [sectorData, setSectorData] = useState<Record<string, any[]>>({});
  const [scanViewSize, setScanViewSize] = useState({ width: 0, height: 0 });
  const lastScanned = useRef<string>("");
  const scanCooldown = useRef(false);

  // ── 스캔 처리 ──
  const handleBarcodeScan = async ({ data, bounds }: { data: string; bounds?: { origin: { x: number; y: number }; size: { width: number; height: number } } }) => {
    // 박스 영역 밖 바코드 무시
    if (bounds) {
      const cx = bounds.origin.x + bounds.size.width / 2;
      const cy = bounds.origin.y + bounds.size.height / 2;
      if (cx < BOX_LEFT || cx > BOX_RIGHT || cy < BOX_TOP || cy > BOX_BOTTOM) return;
    }
    // 같은 바코드는 2초간 중복 차단, 다른 바코드는 즉시 허용
    if (data === lastScanned.current && scanCooldown.current) return;
    scanCooldown.current = true;
    lastScanned.current = data;
    setTimeout(() => { scanCooldown.current = false; }, 2000);

    try {
      const drum = await parseBarcodeText(data);
      setBatch((prev) => {
        if (prev.some((d) => d.lot === drum.lot)) {
          Alert.alert("중복", `${drum.lot} 이미 스캔됨`);
          return prev;
        }
        return [...prev, drum];
      });
    } catch (e: any) {
      Alert.alert("스캔 오류", e.message);
    }
  };

  // ── 섹터 선택 후 저장 ──
  const handleSectorSelect = async (sector: string) => {
    if (batch.length === 0) return;
    setMode("idle");
    setLoading(true);
    try {
      await registerDrums(batch, sector);
      const count = batch.length;
      setBatch([]);
      lastScanned.current = "";
      Alert.alert(
        "저장 완료",
        sector === CHECKOUT
          ? `${count}드럼 라인입고 처리 완료`
          : `${count}드럼 → ${sector} 등록 완료`
      );
    } catch (e: any) {
      Alert.alert("저장 실패", e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── 재고 현황 조회 ──
  const loadStatus = async () => {
    setLoading(true);
    try {
      const data = await getSectorInventory();
      setSectorData(data);
      setMode("status");
    } catch (e: any) {
      Alert.alert("조회 실패", e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── 카메라 권한 ──
  if (!permission) return <View />;
  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.permText}>카메라 권한이 필요합니다.</Text>
        <TouchableOpacity style={styles.btn} onPress={requestPermission}>
          <Text style={styles.btnText}>권한 허용</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ── 스캔 화면 ──
  if (mode === "scanning") {
    // CSS의 top:50% left:50% translate(-50%,-50%) 와 동일한 원리
    const BOX_W = 340, BOX_H = 130;

    return (
      <View style={{ flex: 1, backgroundColor: "#000" }}>
        <Stack.Screen options={{ title: "바코드 스캔", headerShown: false }} />
        <CameraView
          style={StyleSheet.absoluteFillObject}
          facing="back"
          onBarcodeScanned={handleBarcodeScan}
          barcodeScannerSettings={{ barcodeTypes: ["pdf417", "code128", "code39", "qr", "datamatrix", "aztec", "ean13", "ean8"] }}
        />
        {/* 스캔 가이드 박스: top/left 50% + 음수 마진으로 정중앙 고정 */}
        <View
          pointerEvents="none"
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: BOX_W,
            height: BOX_H,
            marginTop: -BOX_H / 2,
            marginLeft: -BOX_W / 2,
            borderWidth: 2,
            borderColor: "#fff",
            borderRadius: 8,
          }}
        />
        {/* 배치 카운터 */}
        <View style={styles.batchBadge}>
          <Text style={styles.batchBadgeText}>스캔됨: {batch.length}드럼</Text>
        </View>
        {/* 최근 스캔 */}
        {batch.length > 0 && (
          <View style={styles.lastScannedBox}>
            <Text style={styles.lastScannedText}>
              최근: {batch[batch.length - 1].lot} ({batch[batch.length - 1].maker})
            </Text>
          </View>
        )}
        {/* 하단 버튼 */}
        <View style={styles.scanFooter}>
          <TouchableOpacity style={styles.cancelBtn} onPress={() => setMode("idle")}>
            <Text style={styles.cancelBtnText}>취소</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.doneBtn, batch.length === 0 && styles.btnDisabled]}
            onPress={() => { if (batch.length > 0) setMode("sectorPick"); }}
            disabled={batch.length === 0}
          >
            <Text style={styles.doneBtnText}>완료 ({batch.length})</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // ── 섹터 선택 모달 ──
  const SectorModal = () => (
    <Modal visible={mode === "sectorPick"} animationType="slide" transparent>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>{batch.length}드럼 → 섹터 선택</Text>
          <ScrollView>
            {SECTORS.map((s) => (
              <TouchableOpacity key={s} style={styles.sectorBtn} onPress={() => handleSectorSelect(s)}>
                <Text style={styles.sectorBtnText}>{s}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity style={[styles.sectorBtn, styles.checkoutBtn]} onPress={() => handleSectorSelect(CHECKOUT)}>
              <Text style={[styles.sectorBtnText, { color: "#fff" }]}>{CHECKOUT}</Text>
            </TouchableOpacity>
          </ScrollView>
          <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setMode("scanning")}>
            <Text style={styles.modalCancelText}>돌아가기</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  // ── 재고 현황 화면 ──
  if (mode === "status") {
    const sectorKeys = Object.keys(sectorData);
    return (
      <>
        <Stack.Screen options={{ title: "재고 현황" }} />
        <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
          <TouchableOpacity style={styles.backBtn} onPress={() => setMode("idle")}>
            <Text style={styles.backBtnText}>← 뒤로</Text>
          </TouchableOpacity>
          {sectorKeys.length === 0 ? (
            <Text style={styles.emptyText}>보관 중인 드럼 없음</Text>
          ) : (
            sectorKeys.map((sector) => (
              <View key={sector} style={styles.sectorCard}>
                <View style={styles.sectorHeader}>
                  <Text style={styles.sectorName}>{sector}</Text>
                  <Text style={styles.sectorCount}>{sectorData[sector].length}드럼</Text>
                </View>
                {sectorData[sector].map((drum: any, i: number) => (
                  <View key={i} style={styles.drumRow}>
                    <Text style={styles.drumLot}>{drum.lot}</Text>
                    <Text style={styles.drumProduct}>{drum.product}</Text>
                    <Text style={styles.drumMaker}>{drum.maker}</Text>
                  </View>
                ))}
              </View>
            ))
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      </>
    );
  }

  // ── 메인(idle) 화면 ──
  return (
    <>
      <Stack.Screen options={{ title: "재고 관리" }} />
      <SectorModal />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* 현재 배치 */}
        {batch.length > 0 && (
          <View style={styles.batchCard}>
            <View style={styles.batchHeader}>
              <Text style={styles.batchTitle}>스캔 목록 ({batch.length}드럼)</Text>
              <TouchableOpacity onPress={() => { setBatch([]); lastScanned.current = ""; }}>
                <Text style={styles.clearText}>전체 삭제</Text>
              </TouchableOpacity>
            </View>
            {batch.map((drum, i) => (
              <View key={i} style={styles.drumRow}>
                <Text style={styles.drumLot}>{drum.lot}</Text>
                <Text style={styles.drumProduct}>{drum.product}</Text>
                <Text style={styles.drumMaker}>{drum.maker}</Text>
                <TouchableOpacity onPress={() => setBatch((prev) => prev.filter((_, idx) => idx !== i))}>
                  <Text style={styles.removeText}>삭제</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {/* 스캔 버튼 */}
        <TouchableOpacity
          style={[styles.btn, styles.scanBtn]}
          onPress={() => setMode("scanning")}
          disabled={loading}
        >
          <Text style={styles.btnText}>
            {batch.length > 0 ? `스캔 계속 (현재 ${batch.length}드럼)` : "바코드 스캔 시작"}
          </Text>
        </TouchableOpacity>

        {/* 섹터 지정 버튼 */}
        {batch.length > 0 && (
          <TouchableOpacity
            style={[styles.btn, styles.registerBtn]}
            onPress={() => setMode("sectorPick")}
            disabled={loading}
          >
            <Text style={styles.btnText}>섹터 선택 → 저장</Text>
          </TouchableOpacity>
        )}

        {/* 재고 현황 버튼 */}
        <TouchableOpacity
          style={[styles.btn, styles.statusBtn]}
          onPress={loadStatus}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.btnText}>섹터별 재고 현황</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  content: { padding: 16, gap: 12 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  permText: { fontSize: 16, color: COLORS.textPrimary, marginBottom: 16 },

  // 스캔 박스 - 픽셀 좌표로 정확히 배치
  scanBox: { position: "absolute", top: BOX_TOP, left: BOX_LEFT, width: BOX_W, height: BOX_H, borderWidth: 2, borderColor: "#fff", borderRadius: 8 },
  batchBadge: { position: "absolute", top: 60, alignSelf: "center", backgroundColor: "rgba(0,0,0,0.7)", paddingHorizontal: 16, paddingVertical: 6, borderRadius: 20 },
  batchBadgeText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  lastScannedBox: { position: "absolute", bottom: 120, left: 16, right: 16, backgroundColor: "rgba(0,0,0,0.7)", padding: 10, borderRadius: 8 },
  lastScannedText: { color: "#4AFF91", fontSize: 13, textAlign: "center" },
  scanFooter: { position: "absolute", bottom: 40, left: 16, right: 16, flexDirection: "row", gap: 12 },
  cancelBtn: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", paddingVertical: 16, borderRadius: 12, alignItems: "center", borderWidth: 1, borderColor: "#fff" },
  cancelBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  doneBtn: { flex: 2, backgroundColor: COLORS.primary, paddingVertical: 16, borderRadius: 12, alignItems: "center" },
  doneBtnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  btnDisabled: { backgroundColor: "#666" },

  // 섹터 모달
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: "80%" },
  modalTitle: { fontSize: 18, fontWeight: "700", color: COLORS.textPrimary, marginBottom: 16, textAlign: "center" },
  sectorBtn: { paddingVertical: 14, paddingHorizontal: 16, borderRadius: 10, backgroundColor: COLORS.surface, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  sectorBtnText: { fontSize: 16, fontWeight: "600", color: COLORS.textPrimary, textAlign: "center" },
  checkoutBtn: { backgroundColor: "#E53935" },
  modalCancelBtn: { marginTop: 8, paddingVertical: 14, alignItems: "center" },
  modalCancelText: { color: COLORS.textSecondary, fontSize: 15 },

  // 배치 카드
  batchCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, elevation: 2 },
  batchHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  batchTitle: { fontSize: 15, fontWeight: "700", color: COLORS.textPrimary },
  clearText: { fontSize: 13, color: COLORS.error, fontWeight: "600" },
  drumRow: { flexDirection: "row", alignItems: "center", paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: COLORS.border, gap: 6 },
  drumLot: { flex: 2, fontSize: 12, fontWeight: "600", color: COLORS.textPrimary },
  drumProduct: { flex: 1, fontSize: 12, color: COLORS.textSecondary },
  drumMaker: { flex: 1.5, fontSize: 11, color: COLORS.textSecondary },
  removeText: { fontSize: 12, color: COLORS.error, fontWeight: "600" },

  // 버튼
  btn: { paddingVertical: 16, borderRadius: 12, alignItems: "center", elevation: 3 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  scanBtn: { backgroundColor: COLORS.primary },
  registerBtn: { backgroundColor: "#2E7D32" },
  statusBtn: { backgroundColor: "#1565C0" },

  // 현황
  backBtn: { marginBottom: 16 },
  backBtnText: { fontSize: 15, color: COLORS.primary, fontWeight: "600" },
  emptyText: { fontSize: 15, color: COLORS.textSecondary, textAlign: "center", marginTop: 40 },
  sectorCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, marginBottom: 12, elevation: 2 },
  sectorHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  sectorName: { fontSize: 16, fontWeight: "700", color: COLORS.textPrimary },
  sectorCount: { fontSize: 14, fontWeight: "600", color: COLORS.primary },
});
