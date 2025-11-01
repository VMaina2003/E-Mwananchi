import json, re, time
from django.conf import settings
from google import genai
from rapidfuzz import process, fuzz

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def classify_department(title: str, description: str, known_departments: list):
    prompt = f"""
You are an AI assistant for E-Mwananchi.
Classify this report and return STRICT JSON only:

{{
    "verified": true or false,
    "confidence": 0.0 to 1.0,
    "predicted_department": "Department Name from the known list",
    "predicted_county": "County Name"
}}

Known Departments: {known_departments}
Report Title: {title}
Description: {description}
"""
    models_to_try = ["models/gemini-2.5-pro", "models/gemini-2.5-flash"]

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            raw = getattr(response, "text", "").strip()
            if not raw:
                continue

            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                ai_department = data.get("predicted_department")
                matched_department = match_department(ai_department, known_departments)

                return {
                    "verified": data.get("verified", False),
                    "confidence": float(data.get("confidence", 0.0)),
                    "predicted_department": matched_department,
                    "predicted_county": data.get("predicted_county"),
                }

        except Exception as e:
            if "UNAVAILABLE" in str(e):
                time.sleep(3)
            continue

    # fallback if AI fails
    return {
        "verified": False,
        "confidence": 0.0,
        "predicted_department": None,
        "predicted_county": None,
    }
    
def match_department(ai_department, known_departments):
    """
    Fuzzy match AI-predicted department with known departments
    """
    if not ai_department:
        return None
    
    # Simple exact match first
    if ai_department in known_departments:
        return ai_department
    
    # Fuzzy matching as fallback
    try:
        best_match = process.extractOne(ai_department, known_departments, scorer=fuzz.token_sort_ratio)
        if best_match and best_match[1] > 80:  # 80% similarity threshold
            return best_match[0]
    except:
        pass
    
    return None
