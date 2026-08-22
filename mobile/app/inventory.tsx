import React, { useState, useRef, useEffect } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  FlatList,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  Vibration,
  View,
} from "react-native";
import { Stack } from "expo-router";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as FileSystem from "expo-file-system";
import TextRecognition, { type TextBlock } from "@react-native-ml-kit/text-recognition";

import { COLORS } from "../src/constants/config";
import { registerDrums, getSectorInventory, type DrumItem } from "../src/services/api";

// ── 제조사 코드 ──
const MAKER_MAP: Record<string, string> = {
  G: "고려(KCC)", D: "대한(노루)", K: "건설(제비)",
  S: "삼화", Y: "애경", P: "동주(PPG)",
};

// ── OCR 추출 패턴 ──
// LOT: 영문1 + 숫자2 + 영문1 + 숫자5 = 9자  예) P26D03917
const LOT_RE = /[A-Z][0-9]{2}[A-Z][0-9]{5}/;
// 품명: 영문1 + 숫자1 + 영문1 + (숫자또는영문){3} + 영문1 = 7자  예) P7M122B, P7YA83B
const ITEM_RE = /[A-Z][0-9][A-Z][A-Z0-9]{3}[A-Z]/;
const LOT_KEYWORDS = ["DRUM LOT", "LOT.NO", "DRUM NO", "LOT NO", "LOT", "롯트번호"];

function parseOcrBlocks(blocks: TextBlock[]): DrumItem | null {
  if (!blocks?.length) return null;
  const allText = blocks.map(b => b.text).join("\n");
  // 공백·하이픈 제거 + 대문자 통일
  const flat = allText.replace(/[-\s]/g, "").toUpperCase();

  // 1. LOT 추출 — 패턴 우선
  let lot = "";
  const lotMatch = flat.match(LOT_RE);
  if (lotMatch) {
    lot = lotMatch[0];
  } else {
    const upper = allText.toUpperCase();
    for (const kw of LOT_KEYWORDS) {
      const idx = upper.indexOf(kw);
      if (idx !== -1) {
        const after = allText.slice(idx + kw.length).replace(/[-\s]/g, "").toUpperCase();
        const m = after.match(LOT_RE);
        if (m) { lot = m[0]; break; }
      }
    }
  }
  if (!lot) return null;

  // 2. 품명 추출 — 패턴 우선, 실패 시 가장 큰 바운딩 박스 블록
  let product = "";
  const itemMatch = flat.match(ITEM_RE);
  if (itemMatch) {
    product = itemMatch[0];
  } else {
    const sorted = [...blocks]
      .filter(b => b.frame?.width && b.frame?.height)
      .sort((a, b_) => (b_.frame!.width * b_.frame!.height) - (a.frame!.width * a.frame!.height));
    if (sorted.length > 0) product = sorted[0].text.replace(/[-\s]/g, "").toUpperCase();
  }

  return { lot, product: product.replace(/[-\s]/g, ""), maker: MAKER_MAP[lot[0]] ?? lot[0] };
}

const SECTORS = [
  "신나자리", "0~3번자리", "4~6번자리", "7A~C자리", "7D~Z자리",
  "8번자리", "9번자리", "반품자리", "CW2", "CP5", "창고뒤",
];
const CHECKOUT = "라인입고";
type Mode = "idle" | "scanning" | "sectorPick" | "status";

export default function InventoryScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [mode, setMode] = useState<Mode>("idle");
  const [batch, setBatch] = useState<DrumItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [sectorData, setSectorData] = useState<Record<string, any[]>>({});
  const [editingItem, setEditingItem] = useState<{ index: number; lot: string; product: string } | null>(null);

  const cameraRef = useRef<CameraView>(null);
  const batchRef = useRef<DrumItem[]>([]);
  const processingRef = useRef(false);
  const cooldownRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const flashAnim = useRef(new Animated.Value(0)).current;

  // batchRef를 batch와 동기화 (클로저 stale 방지)
  useEffect(() => { batchRef.current = batch; }, [batch]);

  // 권한 자동 요청
  useEffect(() => {
    if (permission && !permission.granted && !permission.canAskAgain) return;
    if (!permission?.granted) requestPermission();
  }, [permission]);

  // 스캔 모드 진입/종료 시 OCR 루프 시작/정지
  useEffect(() => {
    if (mode === "scanning") {
      intervalRef.current = setInterval(runOcr, 900);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [mode]);

  const triggerFeedback = () => {
    Vibration.vibrate([0, 80, 60, 80]);
    Animated.sequence([
      Animated.timing(flashAnim, { toValue: 0.4, duration: 80, useNativeDriver: true }),
      Animated.timing(flashAnim, { toValue: 0, duration: 250, useNativeDriver: true }),
    ]).start();
  };

  const runOcr = async () => {
    if (processingRef.current || cooldownRef.current || !cameraRef.current) return;
    processingRef.current = true;
    let uri: string | undefined;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.7,
        skipMetadata: true,
        shutterSound: false,
      });
      uri = photo?.uri;
      if (!uri) return;

      const result = await TextRecognition.recognize(uri);
      const parsed = parseOcrBlocks(result.blocks ?? []);

      if (parsed && !batchRef.current.some(d => d.lot === parsed.lot)) {
        triggerFeedback();
        cooldownRef.current = true;
        setTimeout(() => { cooldownRef.current = false; }, 1500);
        setBatch(prev => [...prev, parsed]);
      }
    } catch (_) {
      // OCR 오류 무시 (다음 주기에 재시도)
    } finally {
      processingRef.current = false;
      if (uri) FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});
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
      Alert.alert(
        "저장 완료",
        sector === CHECKOUT ? `${count}드럼 라인입고 처리 완료` : `${count}드럼 → ${sector} 등록 완료`
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
    return (
      <View style={{ flex: 1, backgroundColor: "#111" }}>
        <Stack.Screen options={{ title: "라벨 OCR 스캔", headerShown: true }} />

        {/* 상단: 누적 스캔 리스트 */}
        <View style={styles.scanListArea}>
          <View style={styles.scanListHeader}>
            <Text style={styles.scanListCount}>총 {batch.length}건 스캔됨</Text>
            <TouchableOpacity
              style={[styles.doneSmallBtn, batch.length === 0 && styles.btnDisabled]}
              onPress={() => { if (batch.length > 0) setMode("sectorPick"); }}
              disabled={batch.length === 0}
            >
              <Text style={styles.doneSmallBtnText}>완료 ({batch.length})</Text>
            </TouchableOpacity>
          </View>
          {batch.length === 0 ? (
            <Text style={styles.scanListEmpty}>라벨을 카메라에 비춰주세요</Text>
          ) : (
            <FlatList
              data={[...batch].reverse()}
              keyExtractor={(item) => item.lot}
              renderItem={({ item, index }) => {
                const realIndex = batch.length - 1 - index;
                return (
                  <TouchableOpacity
                    style={styles.scanListItem}
                    onPress={() => setEditingItem({ index: realIndex, lot: item.lot, product: item.product })}
                  >
                    <Text style={styles.scanListNum}>{batch.length - index}</Text>
                    <Text style={styles.scanListProduct}>{item.product || "-"}</Text>
                    <Text style={styles.scanListLot}>{item.lot}</Text>
                    <TouchableOpacity onPress={() => setBatch(prev => prev.filter(d => d.lot !== item.lot))}>
                      <Text style={styles.scanListDelete}>✕</Text>
                    </TouchableOpacity>
                  </TouchableOpacity>
                );
              }}
            />
          )}
        </View>

        {/* 하단: 카메라 + 가이드 박스 */}
        <View style={styles.cameraArea}>
          <CameraView ref={cameraRef} style={{ flex: 1 }} facing="back" />
          {/* 가이드 오버레이 */}
          <View pointerEvents="none" style={[StyleSheet.absoluteFillObject, styles.guideOverlay]}>
            <View style={styles.guideBox} />
            <Text style={styles.guideHint}>품명·LOT 라벨을 박스 안에 맞추세요</Text>
          </View>
          {/* 인식 성공 플래시 */}
          <Animated.View
            pointerEvents="none"
            style={[StyleSheet.absoluteFillObject, { backgroundColor: "#4AFF91", opacity: flashAnim }]}
          />
        </View>

        {/* 취소 버튼 */}
        <TouchableOpacity style={styles.scanCancelBtn} onPress={() => setMode("idle")}>
          <Text style={styles.cancelBtnText}>취소</Text>
        </TouchableOpacity>
        <EditModal />
      </View>
    );
  }

  // ── 항목 편집 모달 ──
  const EditModal = () => (
    <Modal visible={editingItem !== null} animationType="fade" transparent>
      <View style={styles.modalOverlay}>
        <View style={styles.editCard}>
          <Text style={styles.editTitle}>항목 수정</Text>
          <Text style={styles.editLabel}>품명</Text>
          <TextInput
            style={styles.editInput}
            value={editingItem?.product ?? ""}
            onChangeText={v => setEditingItem(prev => prev ? { ...prev, product: v.replace(/[-\s]/g, "").toUpperCase() } : prev)}
            autoCapitalize="characters"
            placeholder="예) P7Y751Y"
          />
          <Text style={styles.editLabel}>LOT번호</Text>
          <TextInput
            style={styles.editInput}
            value={editingItem?.lot ?? ""}
            onChangeText={v => setEditingItem(prev => prev ? { ...prev, lot: v.replace(/[-\s]/g, "").toUpperCase() } : prev)}
            autoCapitalize="characters"
            placeholder="예) P26D03917"
          />
          <View style={{ flexDirection: "row", gap: 10, marginTop: 16 }}>
            <TouchableOpacity style={[styles.editBtn, { backgroundColor: "#888" }]} onPress={() => setEditingItem(null)}>
              <Text style={styles.editBtnText}>취소</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.editBtn, { flex: 2, backgroundColor: COLORS.primary }]}
              onPress={() => {
                if (!editingItem) return;
                setBatch(prev => {
                  const next = [...prev];
                  next[editingItem.index] = {
                    ...next[editingItem.index],
                    lot: editingItem.lot,
                    product: editingItem.product,
                    maker: MAKER_MAP[editingItem.lot[0]] ?? next[editingItem.index].maker,
                  };
                  return next;
                });
                setEditingItem(null);
              }}
            >
              <Text style={styles.editBtnText}>저장</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );

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
      <EditModal />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {batch.length > 0 && (
          <View style={styles.batchCard}>
            <View style={styles.batchHeader}>
              <Text style={styles.batchTitle}>스캔 목록 ({batch.length}드럼)</Text>
              <TouchableOpacity onPress={() => setBatch([])}>
                <Text style={styles.clearText}>전체 삭제</Text>
              </TouchableOpacity>
            </View>
            {batch.map((drum, i) => (
              <TouchableOpacity key={i} style={styles.drumRow} onPress={() => setEditingItem({ index: i, lot: drum.lot, product: drum.product })}>
                <Text style={styles.drumLot}>{drum.lot}</Text>
                <Text style={styles.drumProduct}>{drum.product}</Text>
                <Text style={styles.drumMaker}>{drum.maker}</Text>
                <TouchableOpacity onPress={() => setBatch(prev => prev.filter((_, idx) => idx !== i))}>
                  <Text style={styles.removeText}>삭제</Text>
                </TouchableOpacity>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <TouchableOpacity style={[styles.btn, styles.scanBtn]} onPress={() => setMode("scanning")} disabled={loading}>
          <Text style={styles.btnText}>
            {batch.length > 0 ? `스캔 계속 (현재 ${batch.length}드럼)` : "라벨 OCR 스캔 시작"}
          </Text>
        </TouchableOpacity>

        {batch.length > 0 && (
          <TouchableOpacity style={[styles.btn, styles.registerBtn]} onPress={() => setMode("sectorPick")} disabled={loading}>
            <Text style={styles.btnText}>섹터 선택 → 저장</Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity style={[styles.btn, styles.statusBtn]} onPress={loadStatus} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>섹터별 재고 현황</Text>}
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

  // 스캔 화면 - 상단 리스트
  scanListArea: { height: 200, backgroundColor: "#1a1a1a", borderBottomWidth: 1, borderBottomColor: "#333" },
  scanListHeader: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#333",
  },
  scanListCount: { color: "#fff", fontSize: 13, fontWeight: "700" },
  doneSmallBtn: { backgroundColor: COLORS.primary, paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8 },
  doneSmallBtnText: { color: "#fff", fontSize: 13, fontWeight: "700" },
  scanListEmpty: { color: "#888", fontSize: 13, textAlign: "center", marginTop: 24 },
  scanListItem: {
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 12, paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: "#2a2a2a", gap: 8,
  },
  scanListNum: { width: 22, color: "#888", fontSize: 12, textAlign: "center" },
  scanListProduct: { flex: 1.2, color: "#4AFF91", fontSize: 13, fontWeight: "700" },
  scanListLot: { flex: 1.5, color: "#ccc", fontSize: 12 },
  scanListDelete: { color: "#ff5555", fontSize: 16, paddingHorizontal: 4 },

  // 스캔 화면 - 카메라
  cameraArea: { flex: 1 },
  guideOverlay: { alignItems: "center", justifyContent: "center", gap: 12 },
  guideBox: { width: 280, height: 160, borderWidth: 2, borderColor: "#fff", borderRadius: 10 },
  guideHint: { color: "rgba(255,255,255,0.8)", fontSize: 12, textAlign: "center" },
  scanCancelBtn: {
    backgroundColor: "rgba(0,0,0,0.85)", paddingVertical: 16,
    alignItems: "center", borderTopWidth: 1, borderTopColor: "#333",
  },
  cancelBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  // 편집 모달
  editCard: { backgroundColor: "#fff", borderRadius: 16, padding: 20, margin: 24 },
  editTitle: { fontSize: 17, fontWeight: "700", color: COLORS.textPrimary, marginBottom: 16, textAlign: "center" },
  editLabel: { fontSize: 13, color: COLORS.textSecondary, marginBottom: 4 },
  editInput: {
    borderWidth: 1, borderColor: COLORS.border, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 15,
    color: COLORS.textPrimary, marginBottom: 12,
  },
  editBtn: { flex: 1, paddingVertical: 12, borderRadius: 8, alignItems: "center" },
  editBtnText: { color: "#fff", fontSize: 15, fontWeight: "700" },

  // 섹터 모달
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: "80%" },
  modalTitle: { fontSize: 18, fontWeight: "700", color: COLORS.textPrimary, marginBottom: 16, textAlign: "center" },
  sectorBtn: {
    paddingVertical: 14, paddingHorizontal: 16, borderRadius: 10,
    backgroundColor: COLORS.surface, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border,
  },
  sectorBtnText: { fontSize: 16, fontWeight: "600", color: COLORS.textPrimary, textAlign: "center" },
  checkoutBtn: { backgroundColor: "#E53935" },
  modalCancelBtn: { marginTop: 8, paddingVertical: 14, alignItems: "center" },
  modalCancelText: { color: COLORS.textSecondary, fontSize: 15 },

  // 배치 카드 (idle 화면)
  batchCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, elevation: 2 },
  batchHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  batchTitle: { fontSize: 15, fontWeight: "700", color: COLORS.textPrimary },
  clearText: { fontSize: 13, color: COLORS.error, fontWeight: "600" },
  drumRow: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: COLORS.border, gap: 6,
  },
  drumLot: { flex: 2, fontSize: 12, fontWeight: "600", color: COLORS.textPrimary },
  drumProduct: { flex: 1, fontSize: 12, color: COLORS.textSecondary },
  drumMaker: { flex: 1.5, fontSize: 11, color: COLORS.textSecondary },
  removeText: { fontSize: 12, color: COLORS.error, fontWeight: "600" },

  // 버튼
  btn: { paddingVertical: 16, borderRadius: 12, alignItems: "center", elevation: 3 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  btnDisabled: { backgroundColor: "#666" },
  scanBtn: { backgroundColor: COLORS.primary },
  registerBtn: { backgroundColor: "#2E7D32" },
  statusBtn: { backgroundColor: "#1565C0" },

  // 재고 현황
  backBtn: { marginBottom: 16 },
  backBtnText: { fontSize: 15, color: COLORS.primary, fontWeight: "600" },
  emptyText: { fontSize: 15, color: COLORS.textSecondary, textAlign: "center", marginTop: 40 },
  sectorCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, marginBottom: 12, elevation: 2 },
  sectorHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  sectorName: { fontSize: 16, fontWeight: "700", color: COLORS.textPrimary },
  sectorCount: { fontSize: 14, fontWeight: "600", color: COLORS.primary },
});
