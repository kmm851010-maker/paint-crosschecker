import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { COLORS, STATUS_COLORS, STATUS_TEXT_COLORS } from "@/constants/config";
import type { ResultItem } from "@/services/api";

interface ResultTableProps {
  results: ResultItem[];
}

export default function ResultTable({ results }: ResultTableProps) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator>
      <View>
        {/* Header */}
        <View style={styles.headerRow}>
          {["No.", "라인", "위치", "색상코드", "계획", "입고", "차이", "상태"].map(
            (col) => (
              <View
                key={col}
                style={[styles.cell, col === "색상코드" ? styles.wideCell : null]}
              >
                <Text style={styles.headerText}>{col}</Text>
              </View>
            )
          )}
        </View>

        {/* Data Rows */}
        {results.map((item, idx) => {
          const rowBg = STATUS_COLORS[item.상태] || COLORS.surface;
          const statusColor = STATUS_TEXT_COLORS[item.상태] || COLORS.textPrimary;

          return (
            <View key={idx} style={[styles.dataRow, { backgroundColor: rowBg }]}>
              <View style={styles.cell}>
                <Text style={styles.cellText}>{idx + 1}</Text>
              </View>
              <View style={styles.cell}>
                <Text style={styles.cellText}>{item.라인}</Text>
              </View>
              <View style={styles.cell}>
                <Text style={styles.cellText}>{item.위치}</Text>
              </View>
              <View style={[styles.cell, styles.wideCell]}>
                <Text style={styles.cellText} numberOfLines={1}>
                  {item.색상코드}
                </Text>
              </View>
              <View style={styles.cell}>
                <Text style={styles.cellText}>{item.계획수량}</Text>
              </View>
              <View style={styles.cell}>
                <Text style={styles.cellText}>{item.입고수량}</Text>
              </View>
              <View style={styles.cell}>
                <Text
                  style={[
                    styles.cellText,
                    styles.bold,
                    { color: item.차이 === 0 ? COLORS.success : COLORS.error },
                  ]}
                >
                  {item.차이 > 0 ? `+${item.차이}` : item.차이}
                </Text>
              </View>
              <View style={styles.cell}>
                <Text style={[styles.statusText, { color: statusColor }]}>
                  {item.상태}
                </Text>
              </View>
            </View>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: "row",
    backgroundColor: COLORS.primary,
    borderTopLeftRadius: 8,
    borderTopRightRadius: 8,
  },
  dataRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  cell: {
    width: 60,
    paddingVertical: 10,
    paddingHorizontal: 6,
    alignItems: "center",
    justifyContent: "center",
  },
  wideCell: {
    width: 120,
  },
  headerText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "700",
  },
  cellText: {
    fontSize: 12,
    color: COLORS.textPrimary,
  },
  bold: {
    fontWeight: "700",
  },
  statusText: {
    fontSize: 12,
    fontWeight: "700",
  },
});
