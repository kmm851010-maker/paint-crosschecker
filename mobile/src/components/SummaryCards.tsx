import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { COLORS } from "@/constants/config";
import type { Summary } from "@/services/api";

interface SummaryCardsProps {
  summary: Summary;
}

export default function SummaryCards({ summary }: SummaryCardsProps) {
  const cards = [
    { label: "일치", value: summary.match_count, bg: COLORS.successLight, fg: COLORS.success },
    { label: "초과", value: summary.excess_count, bg: COLORS.warningLight, fg: COLORS.warning },
    { label: "부족", value: summary.short_count, bg: COLORS.errorLight, fg: COLORS.error },
    { label: "미입고", value: summary.missing_count, bg: COLORS.missingLight, fg: COLORS.error },
  ];

  return (
    <View style={styles.container}>
      {cards.map((card) => (
        <View key={card.label} style={[styles.card, { backgroundColor: card.bg }]}>
          <Text style={[styles.value, { color: card.fg }]}>{card.value}</Text>
          <Text style={[styles.label, { color: card.fg }]}>{card.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 16,
  },
  card: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 12,
    borderRadius: 10,
  },
  value: {
    fontSize: 24,
    fontWeight: "800",
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
    marginTop: 2,
  },
});
