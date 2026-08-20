"""
OpenCV 기반 물리적 격자선 감지 및 셀 분할 모듈
이미지 기울기 보정 → 격자선 감지 → 교차점 검출 → 셀 크롭
"""

import math
from io import BytesIO

import cv2
import numpy as np
from PIL import Image


def load_image(image_bytes: bytes) -> np.ndarray:
    """이미지 바이트를 OpenCV 형식으로 로드합니다."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("이미지를 로드할 수 없습니다.")
    return img


def deskew(img: np.ndarray) -> np.ndarray:
    """이미지 기울기를 자동 보정합니다."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)

    if lines is None:
        return img

    angles = []
    for line in lines:
        pts = line[0] if len(line.shape) > 1 else line
        if len(pts) < 4:
            continue
        x1, y1, x2, y2 = int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3])
        if abs(x2 - x1) > abs(y2 - y1):
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            if abs(angle) < 10:
                angles.append(angle)

    if not angles:
        return img

    median_angle = np.median(angles)
    if abs(median_angle) < 0.3:
        return img

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def detect_grid_lines(gray: np.ndarray):
    """수평선과 수직선을 감지합니다."""
    h, w = gray.shape

    # 이진화
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 5
    )

    # 수평선 감지
    h_kernel_len = max(w // 20, 30)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=2)

    # 수직선 감지
    v_kernel_len = max(h // 30, 20)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=2)

    return h_lines, v_lines


def find_intersections(h_lines: np.ndarray, v_lines: np.ndarray) -> list:
    """수평선과 수직선의 교차점을 찾습니다."""
    combined = cv2.bitwise_and(h_lines, v_lines)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    combined = cv2.dilate(combined, kernel, iterations=2)

    result = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = result[0] if len(result) == 2 else result[1]

    points = []
    for cnt in contours:
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(float(M["m10"] / M["m00"]))
            cy = int(float(M["m01"] / M["m00"]))
            points.append((cx, cy))

    return sorted(points, key=lambda p: (int(p[1]), int(p[0])))


def cluster_coordinates(values: list, min_gap: int = 10) -> list:
    """근접한 좌표를 클러스터링합니다."""
    if not values:
        return []
    values = sorted(values)
    clusters = [[values[0]]]
    for v in values[1:]:
        if v - clusters[-1][-1] < min_gap:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [int(float(np.mean(c))) for c in clusters]


def extract_row_col_positions(points: list, img_shape: tuple):
    """교차점에서 행/열 위치를 추출합니다."""
    if not points:
        return [], []

    h, w = img_shape[:2]
    min_gap_x = max(w // 100, 10)
    min_gap_y = max(h // 100, 8)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    col_positions = cluster_coordinates(xs, min_gap_x)
    row_positions = cluster_coordinates(ys, min_gap_y)

    return row_positions, col_positions


def extract_cells(img: np.ndarray, row_positions: list, col_positions: list, padding: int = 2) -> list:
    """
    행/열 위치를 기반으로 개별 셀 이미지를 추출합니다.

    Returns:
        2D 리스트: cells[row_idx][col_idx] = cropped cell image (np.ndarray)
    """
    cells = []
    for i in range(len(row_positions) - 1):
        row_cells = []
        y1 = row_positions[i] + padding
        y2 = row_positions[i + 1] - padding
        if y2 <= y1:
            continue

        for j in range(len(col_positions) - 1):
            x1 = col_positions[j] + padding
            x2 = col_positions[j + 1] - padding
            if x2 <= x1:
                row_cells.append(None)
                continue
            cell_img = img[y1:y2, x1:x2]
            row_cells.append(cell_img)

        if row_cells:
            cells.append(row_cells)

    return cells


def is_cell_blank(cell_img: np.ndarray, threshold: float = 0.98) -> bool:
    """셀이 비어있는지 픽셀 밀도로 판별합니다."""
    if cell_img is None or cell_img.size == 0:
        return True

    gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY) if len(cell_img.shape) == 3 else cell_img
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    white_ratio = np.sum(binary == 255) / binary.size
    return white_ratio >= threshold


def cell_to_bytes(cell_img: np.ndarray) -> bytes:
    """OpenCV 이미지를 JPEG 바이트로 변환합니다."""
    success, buf = cv2.imencode(".jpg", cell_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        raise ValueError("셀 이미지 인코딩 실패")
    return buf.tobytes()


def cell_to_base64_png(cell_img: np.ndarray) -> str:
    """셀 이미지를 base64 PNG 문자열로 변환합니다."""
    import base64
    success, buf = cv2.imencode(".png", cell_img)
    if not success:
        return ""
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def process_plan_image(image_bytes: bytes) -> dict:
    """
    생산계획서 이미지를 처리하여 그리드 정보와 셀을 반환합니다.

    Returns:
        {
            "image": deskewed OpenCV image,
            "rows": row positions,
            "cols": col positions,
            "cells": 2D list of cell images,
            "header_cells": first row cells (for column mapping),
        }
    """
    img = load_image(image_bytes)
    img = deskew(img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h_lines, v_lines = detect_grid_lines(gray)
    points = find_intersections(h_lines, v_lines)

    if len(points) < 4:
        raise ValueError(f"격자 교차점이 부족합니다 ({len(points)}개). 표가 명확한 이미지를 사용하세요.")

    row_positions, col_positions = extract_row_col_positions(points, img.shape)

    if len(row_positions) < 3 or len(col_positions) < 3:
        raise ValueError(f"행({len(row_positions)})또는 열({len(col_positions)})이 부족합니다.")

    cells = extract_cells(img, row_positions, col_positions)

    return {
        "image": img,
        "rows": row_positions,
        "cols": col_positions,
        "cells": cells,
        "header_cells": cells[0] if cells else [],
        "num_rows": len(cells),
        "num_cols": len(col_positions) - 1,
    }
