"""
캡처 이미지 테이블 추출 모듈
Claude Vision API를 사용하여 ERP/엑셀 캡처 이미지에서
표 데이터를 구조화된 JSON으로 변환합니다.
"""

import base64

import anthropic

from modules.vision_ocr import detect_media_type, parse_json_response


TABLE_EXTRACT_PROMPT = """당신은 이미지 속 표(테이블)를 완벽하게 디지털 데이터로 변환하는 전문가입니다.

이 이미지에서 표를 찾아 **모든 셀의 데이터를 한 글자도 빠짐없이** 정확히 추출하세요.

## 추출 규칙

### 1. 헤더(컬럼명) 추출
- 표의 첫 번째 행(또는 병합된 헤더 행)을 컬럼명으로 인식하세요.
- 헤더가 여러 줄로 병합된 경우 하위 컬럼명을 사용하세요.
- 헤더 텍스트는 원본 그대로 유지하세요.

### 2. 데이터 행 추출
- 모든 행을 빠짐없이 추출하세요. 행 하나라도 누락하면 안 됩니다.
- 빈 셀은 빈 문자열("")로 표시하세요.

### 3. 데이터 타입 변환 (매우 중요!)
- 품목코드/색상코드: 영문+숫자 조합은 문자열 그대로 유지 (예: "P7A052D")
- 정수형 숫자 (수량, DRUM수, 번호 등): JSON 숫자형으로 변환 (예: 15, 300)
- 소수점 숫자 (중량, 금액 등): JSON 숫자형으로 변환 (예: 18.5, 1250000.0)
- 천 단위 콤마가 있는 숫자: 콤마 제거 후 숫자형으로 (예: "1,250,000" → 1250000)
- 날짜, 텍스트: 문자열 그대로 유지
- 비슷한 글자 주의: 0(영)과 O(오), 1(일)과 I(아이), 5와 S, 8과 B

### 4. 합계/소계 행
- "합계", "소계", "TOTAL" 등의 행이 있으면 그대로 포함하세요.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만:

{
  "headers": ["컬럼1", "컬럼2", "컬럼3"],
  "rows": [
    ["값1", 숫자값, "값3"],
    ["값1", 숫자값, "값3"]
  ]
}
"""


def extract_table_from_image(
    image_bytes: bytes,
    file_name: str,
    api_key: str,
    model: str = "claude-opus-4-8",
) -> dict:
    """
    캡처 이미지에서 표 데이터를 추출합니다.

    Returns:
        {"headers": [...], "rows": [[...], ...]}
    """
    client = anthropic.Anthropic(api_key=api_key)
    b64_image = base64.standard_b64encode(image_bytes).decode("utf-8")
    media_type = detect_media_type(file_name)

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": TABLE_EXTRACT_PROMPT,
                    },
                ],
            }
        ],
    )

    text = ""
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text = getattr(block, "text", "")
            if text:
                break

    if not text:
        raise ValueError("테이블 추출 응답에서 텍스트를 찾을 수 없습니다.")

    data = parse_json_response(text)

    if "headers" not in data or "rows" not in data:
        raise ValueError("응답에 headers 또는 rows가 없습니다.")

    return data
