import React from "react";
import {
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "@/constants/config";

interface FileUploadCardProps {
  title: string;
  icon: keyof typeof Ionicons.glyphMap;
  fileName?: string;
  fileUri?: string;
  isImage?: boolean;
  onPickImage: () => void;
  onPickFile?: () => void;
  onClear: () => void;
}

export default function FileUploadCard({
  title,
  icon,
  fileName,
  fileUri,
  isImage,
  onPickImage,
  onPickFile,
  onClear,
}: FileUploadCardProps) {
  const hasFile = !!fileUri;

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{title}</Text>

      {hasFile ? (
        <View style={styles.previewContainer}>
          {isImage && fileUri ? (
            <Image source={{ uri: fileUri }} style={styles.preview} resizeMode="contain" />
          ) : (
            <View style={styles.fileInfo}>
              <Ionicons name="document-text" size={40} color={COLORS.primary} />
              <Text style={styles.fileName} numberOfLines={2}>
                {fileName}
              </Text>
            </View>
          )}
          <TouchableOpacity style={styles.clearButton} onPress={onClear}>
            <Ionicons name="close-circle" size={24} color={COLORS.error} />
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.buttonRow}>
          <TouchableOpacity style={styles.uploadButton} onPress={onPickImage}>
            <Ionicons name="camera" size={24} color={COLORS.primary} />
            <Text style={styles.buttonText}>촬영/갤러리</Text>
          </TouchableOpacity>

          {onPickFile && (
            <TouchableOpacity style={styles.uploadButton} onPress={onPickFile}>
              <Ionicons name={icon} size={24} color={COLORS.primary} />
              <Text style={styles.buttonText}>파일 선택</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
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
  title: {
    fontSize: 16,
    fontWeight: "700",
    color: COLORS.textPrimary,
    marginBottom: 12,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 12,
  },
  uploadButton: {
    flex: 1,
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 24,
    borderWidth: 2,
    borderColor: COLORS.border,
    borderStyle: "dashed",
    borderRadius: 10,
    gap: 8,
  },
  buttonText: {
    fontSize: 13,
    color: COLORS.primary,
    fontWeight: "600",
  },
  previewContainer: {
    position: "relative",
  },
  preview: {
    width: "100%",
    height: 180,
    borderRadius: 8,
    backgroundColor: COLORS.background,
  },
  fileInfo: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 20,
    gap: 8,
  },
  fileName: {
    fontSize: 13,
    color: COLORS.textSecondary,
    textAlign: "center",
  },
  clearButton: {
    position: "absolute",
    top: 4,
    right: 4,
    backgroundColor: "rgba(255,255,255,0.9)",
    borderRadius: 12,
  },
});
