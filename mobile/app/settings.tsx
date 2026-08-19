import React, { useEffect, useState } from "react";
import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Stack, router } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { COLORS } from "../src/constants/config";

export interface Slot {
  id: string;
  name: string;
  leftLabel: string;
  rightLabel: string;
}

const SLOTS_KEY = "kg_counter_slots";

export default function SettingsScreen() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [editingSlot, setEditingSlot] = useState<Slot | null>(null);

  useEffect(() => {
    loadSlots();
  }, []);

  const loadSlots = async () => {
    const data = await AsyncStorage.getItem(SLOTS_KEY);
    if (data) {
      setSlots(JSON.parse(data));
    }
  };

  const saveSlots = async (newSlots: Slot[]) => {
    await AsyncStorage.setItem(SLOTS_KEY, JSON.stringify(newSlots));
    setSlots(newSlots);
  };

  const addSlot = () => {
    setEditingSlot({
      id: Date.now().toString(),
      name: "",
      leftLabel: "",
      rightLabel: "",
    });
  };

  const saveEditingSlot = async () => {
    if (!editingSlot) return;
    if (!editingSlot.name.trim()) {
      Alert.alert("입력 필요", "슬롯 이름을 입력하세요.");
      return;
    }

    const exists = slots.find((s) => s.id === editingSlot.id);
    let newSlots: Slot[];
    if (exists) {
      newSlots = slots.map((s) => (s.id === editingSlot.id ? editingSlot : s));
    } else {
      newSlots = [...slots, editingSlot];
    }

    await saveSlots(newSlots);
    setEditingSlot(null);
  };

  const deleteSlot = (id: string) => {
    Alert.alert("삭제", "이 슬롯을 삭제하시겠습니까?", [
      { text: "취소", style: "cancel" },
      {
        text: "삭제",
        style: "destructive",
        onPress: async () => {
          const newSlots = slots.filter((s) => s.id !== id);
          await saveSlots(newSlots);
        },
      },
    ]);
  };

  return (
    <>
      <Stack.Screen options={{ title: "검증 슬롯 관리" }} />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* 슬롯 목록 */}
        {slots.map((slot) => (
          <View key={slot.id} style={styles.slotCard}>
            <View style={styles.slotHeader}>
              <Text style={styles.slotName}>{slot.name}</Text>
              <View style={styles.slotActions}>
                <TouchableOpacity onPress={() => setEditingSlot({ ...slot })}>
                  <Text style={styles.editBtn}>수정</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => deleteSlot(slot.id)}>
                  <Text style={styles.deleteBtn}>삭제</Text>
                </TouchableOpacity>
              </View>
            </View>
            <Text style={styles.slotDetail}>좌측: {slot.leftLabel || "(미설정)"}</Text>
            <Text style={styles.slotDetail}>우측: {slot.rightLabel || "(미설정)"}</Text>
          </View>
        ))}

        {slots.length === 0 && !editingSlot && (
          <Text style={styles.emptyText}>등록된 슬롯이 없습니다.</Text>
        )}

        {/* 슬롯 편집 폼 */}
        {editingSlot && (
          <View style={styles.editCard}>
            <Text style={styles.editTitle}>
              {slots.find((s) => s.id === editingSlot.id) ? "슬롯 수정" : "새 슬롯"}
            </Text>

            <Text style={styles.label}>슬롯 이름</Text>
            <TextInput
              style={styles.input}
              value={editingSlot.name}
              onChangeText={(t) => setEditingSlot({ ...editingSlot, name: t })}
              placeholder=""
            />

            <Text style={styles.label}>좌측 문서명</Text>
            <TextInput
              style={styles.input}
              value={editingSlot.leftLabel}
              onChangeText={(t) => setEditingSlot({ ...editingSlot, leftLabel: t })}
              placeholder=""
            />

            <Text style={styles.label}>우측 문서명</Text>
            <TextInput
              style={styles.input}
              value={editingSlot.rightLabel}
              onChangeText={(t) => setEditingSlot({ ...editingSlot, rightLabel: t })}
              placeholder=""
            />

            <View style={styles.editActions}>
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => setEditingSlot(null)}
              >
                <Text style={styles.cancelButtonText}>취소</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveButton} onPress={saveEditingSlot}>
                <Text style={styles.saveButtonText}>저장</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* 추가 버튼 */}
        {!editingSlot && (
          <TouchableOpacity style={styles.addButton} onPress={addSlot}>
            <Text style={styles.addButtonText}>+ 슬롯 추가</Text>
          </TouchableOpacity>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  content: { padding: 16 },
  slotCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
  },
  slotHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  slotName: { fontSize: 17, fontWeight: "700", color: COLORS.textPrimary },
  slotActions: { flexDirection: "row", gap: 12 },
  editBtn: { fontSize: 14, color: COLORS.primary, fontWeight: "600" },
  deleteBtn: { fontSize: 14, color: COLORS.error, fontWeight: "600" },
  slotDetail: { fontSize: 13, color: COLORS.textSecondary, marginTop: 2 },
  emptyText: {
    textAlign: "center",
    color: COLORS.textSecondary,
    fontSize: 15,
    marginTop: 40,
  },
  editCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 20,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: COLORS.primary,
  },
  editTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: COLORS.primary,
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.textPrimary,
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    marginBottom: 12,
    backgroundColor: COLORS.background,
  },
  editActions: { flexDirection: "row", gap: 12, marginTop: 4 },
  cancelButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: "center",
  },
  cancelButtonText: { color: COLORS.textSecondary, fontWeight: "600" },
  saveButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: COLORS.primary,
    alignItems: "center",
  },
  saveButtonText: { color: "#fff", fontWeight: "700" },
  addButton: {
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: COLORS.primary,
    borderStyle: "dashed",
    alignItems: "center",
    marginTop: 8,
  },
  addButtonText: { color: COLORS.primary, fontSize: 16, fontWeight: "700" },
});
