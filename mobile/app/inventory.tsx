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

import { useSafeAreaInsets } from "react-native-safe-area-context";
import { LightSensor } from "expo-sensors";

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
  "입고존", "신나자리", "0~3번자리", "4~6번자리", "7A~C자리", "7D~Z자리",
  "8번자리", "9번자리", "반품자리", "반품대기", "CW2", "CP5", "창고뒤", "롤반 앞",
];
const CHECKOUT = "라인입고";
type Mode = "idle" | "scanning" | "sectorPick" | "status";

export default function InventoryScreen() {
  const insets = useSafeAreaInsets();
  const [permission, requestPermission] = useCameraPermissions();
  const [mode, setMode] = useState<Mode>("idle");
  const [batch, setBatch] = useState<DrumItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [sectorData, setSectorData] = useState<Record<string, any[]>>({});
  const [editingItem, setEditingItem] = useState<{ index: number; lot: string; product: string } | null>(null);
  const [searchText, setSearchText] = useState("");
  const [sortMode, setSortMode] = useState<"sector" | "maker" | "product">("sector");
  const [selectedLots, setSelectedLots] = useState<Set<string>>(new Set());
  // 토치: "off" | "auto" | "on"
  const [torchMode, setTorchMode] = useState<"off" | "auto" | "on">("off");
  const [autoTorchActive, setAutoTorchActive] = useState(false);

  const cameraRef = useRef<CameraView>(null);
  const batchRef = useRef<DrumItem[]>([]);
  const processingRef = useRef(false);
  const cooldownRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const flashAnim = useRef(new Animated.Value(0)).current;
  const torchModeRef = useRef<"off" | "auto" | "on">("off");

  // torchModeRef를 torchMode와 동기화
  useEffect(() => { torchModeRef.current = torchMode; }, [torchMode]);

  // 오토 모드: LightSensor (Android) 조도 구독
  useEffect(() => {
    if (torchMode !== "auto" || mode !== "scanning") {
      setAutoTorchActive(false);
      return;
    }
    let sub: ReturnType<typeof LightSensor.addListener> | null = null;
    LightSensor.isAvailableAsync().then(available => {
      if (!available) return; // iOS: EXIF fallback (runOcr에서 처리)
      LightSensor.setUpdateInterval(800);
      sub = LightSensor.addListener(({ illuminance }) => {
        setAutoTorchActive(illuminance < 50); // 50 lux 이하 → 토치 ON
      });
    });
    return () => { sub?.remove(); };
  }, [torchMode, mode]);

  // batchRef를 batch와 동기화 (클로저 stale 방지)
  useEffect(() => { batchRef.current = batch; }, [batch]);

  // 권한 자동 요청
  useEffect(() => {
    if (permission && !permission.granted && !permission.canAskAgain) return;
    if (!permission?.granted) requestPermission();
  }, [permission]);

  // 스캔 모드 진입/종료 + 저장 중 OCR 루프 시작/정지
  useEffect(() => {
    if (mode === "scanning" && !loading) {
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
  }, [mode, loading]);

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
      const isAuto = torchModeRef.current === "auto";
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.7,
        skipMetadata: !isAuto, // auto 모드에서는 EXIF 필요 (iOS fallback)
        shutterSound: false,
      });
      uri = photo?.uri;
      if (!uri) return;

      // iOS EXIF fallback: LightSensor 없을 때 EXIF BrightnessValue로 판단
      if (isAuto && photo.exif) {
        const bv: number | undefined = (photo.exif as any).BrightnessValue;
        if (bv !== undefined) {
          setAutoTorchActive(bv < 2.0); // 2.0 EV 이하 → 어두움
        }
      }

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
    setMode("scanning");
    setLoading(true);
    try {
      await registerDrums(batch, sector);
      const count = batch.length;
      setBatch([]);
      Alert.alert(
        "저장 완료",
        sector === CHECKOUT ? `${count}드럼 라인입고 처리 완료` : `${count}드럼 → ${sector} 등록 완료\n계속 스캔할 수 있습니다.`
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

        {/* 하단: 카메라 */}
        <View style={styles.cameraArea}>
          <CameraView
            ref={cameraRef}
            style={{ flex: 1 }}
            facing="back"
            enableTorch={torchMode === "on" || (torchMode === "auto" && autoTorchActive)}
          />
          {/* 인식 성공 플래시 */}
          <Animated.View
            pointerEvents="none"
            style={[StyleSheet.absoluteFillObject, { backgroundColor: "#4AFF91", opacity: flashAnim }]}
          />
          {/* 토치 버튼 */}
          <TouchableOpacity
            style={styles.torchBtn}
            onPress={() => setTorchMode(m => m === "off" ? "auto" : m === "auto" ? "on" : "off")}
          >
            <Text style={styles.torchIcon}>
              {torchMode === "on" ? "🔦" : torchMode === "auto" ? "🔆" : "🔦"}
            </Text>
            <Text style={[styles.torchLabel, torchMode !== "off" && styles.torchLabelActive]}>
              {torchMode === "on" ? "ON" : torchMode === "auto" ? `AUTO${autoTorchActive ? "🟡" : "⚪"}` : "OFF"}
            </Text>
          </TouchableOpacity>
        </View>

        {/* 취소 버튼 */}
        <TouchableOpacity style={styles.scanCancelBtn} onPress={() => setMode("idle")}>
          <Text style={styles.cancelBtnText}>취소</Text>
        </TouchableOpacity>

        {/* 저장 중 오버레이 */}
        {loading && (
          <View style={styles.savingOverlay}>
            <ActivityIndicator size="large" color="#fff" />
            <Text style={styles.savingText}>저장 중...</Text>
          </View>
        )}

        <EditModal />
      </View>
    );
  }

  // ── 재고 현황 화면 ──
  if (mode === "status") {
    // 전체 드럼 목록 (sector 필드 추가)
    const allDrums = Object.entries(sectorData).flatMap(([sector, drums]) =>
      drums.map((d: any) => ({ ...d, sector }))
    );
    const totalCount = allDrums.length;

    // 검색 필터
    const filtered = searchText.trim()
      ? allDrums.filter(d =>
          d.lot.toLowerCase().includes(searchText.toLowerCase()) ||
          d.product.toLowerCase().includes(searchText.toLowerCase())
        )
      : allDrums;

    // 그룹화
    const grouped: Record<string, typeof filtered> = {};
    for (const drum of filtered) {
      const key = sortMode === "sector" ? drum.sector
        : sortMode === "maker" ? (drum.maker || "미상")
        : drum.product || "미상";
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(drum);
    }
    const groupKeys = Object.keys(grouped).sort();

    return (
      <>
        <Stack.Screen options={{ title: "재고 현황" }} />
        <View style={styles.container}>
          {/* 헤더 */}
          <View style={styles.statusHeader}>
            <TouchableOpacity onPress={() => setMode("idle")}>
              <Text style={styles.backBtnText}>← 뒤로</Text>
            </TouchableOpacity>
            <Text style={styles.totalCount}>전체 {totalCount}드럼</Text>
          </View>

          {/* 검색창 */}
          <View style={styles.searchRow}>
            <TextInput
              style={styles.searchInput}
              placeholder="품명 또는 LOT 검색..."
              placeholderTextColor="#aaa"
              value={searchText}
              onChangeText={setSearchText}
              autoCapitalize="characters"
              clearButtonMode="while-editing"
            />
          </View>

          {/* 정렬 탭 */}
          <View style={styles.sortRow}>
            {(["sector", "maker", "product"] as const).map((m) => (
              <TouchableOpacity
                key={m}
                style={[styles.sortTab, sortMode === m && styles.sortTabActive]}
                onPress={() => setSortMode(m)}
              >
                <Text style={[styles.sortTabText, sortMode === m && styles.sortTabTextActive]}>
                  {m === "sector" ? "섹터별" : m === "maker" ? "제조사별" : "품목별"}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* 목록 */}
          <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: selectedLots.size > 0 ? 100 + insets.bottom : 40 }}>
            {groupKeys.length === 0 ? (
              <Text style={styles.emptyText}>
                {searchText ? "검색 결과 없음" : "보관 중인 드럼 없음"}
              </Text>
            ) : (
              groupKeys.map((key) => (
                <View key={key} style={styles.sectorCard}>
                  <View style={styles.sectorHeader}>
                    <Text style={styles.sectorName}>{key}</Text>
                    <Text style={styles.sectorCount}>{grouped[key].length}드럼</Text>
                  </View>
                  {/* 테이블 헤더 */}
                  <View style={styles.tableHeader}>
                    <View style={{ width: 28 }} />
                    <Text style={[styles.thCell, { flex: 1.5 }]}>품명</Text>
                    <Text style={[styles.thCell, { flex: 2 }]}>LOT</Text>
                    <Text style={[styles.thCell, { flex: 1.5 }]}>제조사</Text>
                    {sortMode !== "sector" && <Text style={[styles.thCell, { flex: 1.2 }]}>섹터</Text>}
                    <Text style={[styles.thCell, { flex: 1.8 }]}>등록시간</Text>
                  </View>
                  {grouped[key].map((drum: any, i: number) => {
                    const isSelected = selectedLots.has(drum.lot);
                    return (
                      <TouchableOpacity
                        key={i}
                        style={[styles.statusDrumRow, i % 2 === 1 && styles.drumRowAlt, isSelected && styles.drumRowSelected]}
                        onPress={() => setSelectedLots(prev => {
                          const next = new Set(prev);
                          if (next.has(drum.lot)) next.delete(drum.lot);
                          else next.add(drum.lot);
                          return next;
                        })}
                      >
                        <Text style={styles.checkBox}>{isSelected ? "☑" : "☐"}</Text>
                        <Text style={styles.statusProduct}>{drum.product}</Text>
                        <Text style={styles.statusLot}>{drum.lot}</Text>
                        <Text style={[styles.drumMaker, { flex: 1.5 }]}>{drum.maker}</Text>
                        {sortMode !== "sector" && (
                          <Text style={[styles.drumMaker, { flex: 1.2, color: COLORS.primary }]}>{drum.sector}</Text>
                        )}
                        <Text style={[styles.drumMaker, { flex: 1.8, fontSize: 10 }]}>{drum.registered}</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              ))
            )}
          </ScrollView>

          {/* 라인입고 버튼 */}
          {selectedLots.size > 0 && (
            <View style={[styles.checkoutBar, { paddingBottom: 12 + insets.bottom }]}>
              <Text style={styles.checkoutBarText}>{selectedLots.size}드럼 선택됨</Text>
              <TouchableOpacity
                style={styles.checkoutBarBtn}
                onPress={async () => {
                  const drums = allDrums.filter(d => selectedLots.has(d.lot));
                  setLoading(true);
                  try {
                    await registerDrums(drums, CHECKOUT);
                    setSelectedLots(new Set());
                    const data = await getSectorInventory();
                    setSectorData(data);
                    Alert.alert("완료", `${drums.length}드럼 라인입고 처리`);
                  } catch (e: any) {
                    Alert.alert("실패", e.message);
                  } finally {
                    setLoading(false);
                  }
                }}
                disabled={loading}
              >
                {loading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.checkoutBarBtnText}>라인입고</Text>}
              </TouchableOpacity>
            </View>
          )}
        </View>
      </>
    );
  }

  // ── 메인(idle) 화면 ──
  return (
    <>
      <Stack.Screen options={{ title: "KG OPS — 재고 관리" }} />
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
  statusHeader: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  backBtnText: { fontSize: 15, color: COLORS.primary, fontWeight: "600" },
  totalCount: { fontSize: 13, color: COLORS.textSecondary, fontWeight: "600" },
  searchRow: { paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  searchInput: {
    backgroundColor: COLORS.surface, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 8, fontSize: 14, color: COLORS.textPrimary,
    borderWidth: 1, borderColor: COLORS.border,
  },
  sortRow: { flexDirection: "row", paddingHorizontal: 12, paddingVertical: 8, gap: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  sortTab: { flex: 1, paddingVertical: 7, borderRadius: 8, backgroundColor: COLORS.surface, alignItems: "center", borderWidth: 1, borderColor: COLORS.border },
  sortTabActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  sortTabText: { fontSize: 13, fontWeight: "600", color: COLORS.textSecondary },
  sortTabTextActive: { color: "#fff" },
  emptyText: { fontSize: 15, color: COLORS.textSecondary, textAlign: "center", marginTop: 40 },
  sectorCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 12, marginBottom: 12, elevation: 2 },
  sectorHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  sectorName: { fontSize: 15, fontWeight: "700", color: COLORS.textPrimary },
  sectorCount: { fontSize: 13, fontWeight: "600", color: COLORS.primary, backgroundColor: "#EDE7F6", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  tableHeader: { flexDirection: "row", alignItems: "center", paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: COLORS.border, marginBottom: 2 },
  thCell: { fontSize: 11, color: COLORS.textSecondary, fontWeight: "700" },
  statusDrumRow: { flexDirection: "row", alignItems: "center", paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: COLORS.border, gap: 4 },
  statusProduct: { flex: 1.5, fontSize: 14, fontWeight: "700", color: COLORS.textPrimary },
  statusLot: { flex: 2, fontSize: 11, color: COLORS.textSecondary },
  drumRowAlt: { backgroundColor: "rgba(0,0,0,0.02)" },
  drumRowSelected: { backgroundColor: "#EDE7F6" },
  checkBox: { width: 24, fontSize: 16, textAlign: "center", color: COLORS.primary },
  checkoutBar: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: "#1a1a1a", paddingHorizontal: 16, paddingVertical: 12,
    borderTopWidth: 1, borderTopColor: "#333",
  },
  checkoutBarText: { color: "#fff", fontSize: 14, fontWeight: "600" },
  checkoutBarBtn: { backgroundColor: "#E53935", paddingHorizontal: 20, paddingVertical: 10, borderRadius: 8 },
  checkoutBarBtnText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  savingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.65)",
    justifyContent: "center",
    alignItems: "center",
    gap: 16,
  },
  savingText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  torchBtn: {
    position: "absolute", bottom: 12, right: 12,
    alignItems: "center", backgroundColor: "rgba(0,0,0,0.5)",
    borderRadius: 10, paddingHorizontal: 10, paddingVertical: 6,
  },
  torchIcon: { fontSize: 22 },
  torchLabel: { color: "#aaa", fontSize: 11, fontWeight: "700", marginTop: 2 },
  torchLabelActive: { color: "#FFD600" },
});
