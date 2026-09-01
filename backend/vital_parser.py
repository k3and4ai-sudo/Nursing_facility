import json
import re
import requests
from backend.config import (
    OLLAMA_URL, OLLAMA_MODEL,
    TEMP_MIN, TEMP_MAX, BP_SYS_MIN, BP_SYS_MAX, BP_DIA_MIN, BP_DIA_MAX, WEIGHT_MIN, WEIGHT_MAX
)

def extract_vitals_from_text(text: str) -> dict:
    """
    Sends text to Gemma via Ollama to extract vital signs in structured JSON.
    Returns: {
        "temperature": float or None,
        "weight": float or None,
        "systolic": int or None,
        "diastolic": int or None
    }
    """
    prompt = f"""以下は介護施設の利用者が話した内容です。このテキストからバイタルデータ（体温、体重、最高血圧[収縮期血圧]、最低血圧[拡張期血圧]）を抽出し、以下のJSONフォーマットのみで出力してください。数値は必ず半角数値に変換してください。
値が見つからない場合は null に設定してください。
余計な解説、マークダウン記法（```jsonなど）、挨拶は一切含めず、純粋なJSON文字列のみを出力してください。

JSONスキーマ:
{{
  "temperature": 体温（浮動小数点数、例: 36.5）,
  "weight": 体重（浮動小数点数、例: 60.2）,
  "systolic": 最高血圧（整数、例: 120）,
  "diastolic": 最低血圧（整数、例: 80）
}}

テキスト: "{text}"
"""

    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0  # Force deterministic extraction
        }
    }
    
    default_vitals = {
        "temperature": None,
        "weight": None,
        "systolic": None,
        "diastolic": None
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        raw_output = response.json().get("response", "").strip()
        
        # Clean markdown code blocks if the model wrapped JSON
        clean_json = re.sub(r"^```(?:json)?\s*", "", raw_output, flags=re.MULTILINE)
        clean_json = re.sub(r"\s*```$", "", clean_json, flags=re.MULTILINE)
        clean_json = clean_json.strip()
        
        # Find first '{' and last '}' to isolate JSON object if there's other text
        start_idx = clean_json.find('{')
        end_idx = clean_json.rfind('}')
        if start_idx != -1 and end_idx != -1:
            clean_json = clean_json[start_idx:end_idx+1]
            
        parsed_vitals = json.loads(clean_json)
        
        # Verify the structure has our keys
        vitals = {}
        for key in default_vitals.keys():
            val = parsed_vitals.get(key)
            if val is not None:
                # Convert to correct types
                if key in ["temperature", "weight"]:
                    vitals[key] = float(val)
                elif key in ["systolic", "diastolic"]:
                    vitals[key] = int(val)
            else:
                vitals[key] = None
        return vitals

    except Exception as e:
        print(f"Error extracting vitals using Gemma: {e}")
        # Try a regex-based fallback if Ollama/Gemma fails or is slow
        return fallback_regex_parser(text)

def fallback_regex_parser(text: str) -> dict:
    """
    Regex fallback in case the AI model fails to extract vitals.
    """
    vitals = {
        "temperature": None,
        "weight": None,
        "systolic": None,
        "diastolic": None
    }
    
    # Try temp (e.g. 36.5度, 36度5分)
    temp_match = re.search(r"(\d{2})[度\.](\d)(?:分)?", text)
    if temp_match:
        vitals["temperature"] = float(f"{temp_match.group(1)}.{temp_match.group(2)}")
    else:
        temp_match2 = re.search(r"(\d{2}\.\d)度?", text)
        if temp_match2:
            vitals["temperature"] = float(temp_match2.group(1))

    # Try weight (e.g. 60.5キロ, 60kg)
    weight_match = re.search(r"(\d{2,3}(?:\.\d)?)\s*(?:キロ|kg)", text)
    if weight_match:
        vitals["weight"] = float(weight_match.group(1))

    # Try blood pressure (e.g. 120の80, 120/80)
    bp_match = re.search(r"(\d{2,3})\s*(?:の|/|と)\s*(\d{2,3})", text)
    if bp_match:
        vitals["systolic"] = int(bp_match.group(1))
        vitals["diastolic"] = int(bp_match.group(2))
        
    return vitals

def validate_vitals(vitals: dict, user_limits: dict = None) -> tuple[bool, str]:
    """
    Validates vital values and returns (is_alert, alert_reason).
    Uses default thresholds or user-specific ones if provided.
    """
    is_alert = False
    reasons = []
    
    # Extract thresholds
    t_min = user_limits.get("temp_min", TEMP_MIN) if user_limits else TEMP_MIN
    t_max = user_limits.get("temp_max", TEMP_MAX) if user_limits else TEMP_MAX
    sys_min = user_limits.get("bp_sys_min", BP_SYS_MIN) if user_limits else BP_SYS_MIN
    sys_max = user_limits.get("bp_sys_max", BP_SYS_MAX) if user_limits else BP_SYS_MAX
    dia_min = user_limits.get("bp_dia_min", BP_DIA_MIN) if user_limits else BP_DIA_MIN
    dia_max = user_limits.get("bp_dia_max", BP_DIA_MAX) if user_limits else BP_DIA_MAX
    w_min = user_limits.get("weight_min", WEIGHT_MIN) if user_limits else WEIGHT_MIN
    w_max = user_limits.get("weight_max", WEIGHT_MAX) if user_limits else WEIGHT_MAX

    # Check temperature
    temp = vitals.get("temperature")
    if temp is not None:
        if temp > t_max:
            is_alert = True
            reasons.append(f"高熱（{temp}℃）")
        elif temp < t_min:
            is_alert = True
            reasons.append(f"低体温（{temp}℃）")

    # Check blood pressure
    sys = vitals.get("systolic")
    dia = vitals.get("diastolic")
    if sys is not None:
        if sys > sys_max:
            is_alert = True
            reasons.append(f"血圧高[上]（{sys} mmHg）")
        elif sys < sys_min:
            is_alert = True
            reasons.append(f"血圧低[上]（{sys} mmHg）")
    if dia is not None:
        if dia > dia_max:
            is_alert = True
            reasons.append(f"血圧高[下]（{dia} mmHg）")
        elif dia < dia_min:
            is_alert = True
            reasons.append(f"血圧低[下]（{dia} mmHg）")

    # Check weight
    weight = vitals.get("weight")
    if weight is not None:
        if weight > w_max or weight < w_min:
            is_alert = True
            reasons.append(f"体重異常（{weight}kg）")

    return is_alert, "、".join(reasons) if reasons else ""
