import json, re, time, logging
from django.conf import settings
from google import genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from rapidfuzz import process, fuzz

# Set up logging
logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.GEMINI_API_KEY)
def classify_department(title: str, description: str, known_departments: list):
    """
    Enhanced AI classification for reports with better prompting and error handling.
    """
    if not title or not description:
        logger.warning("Empty title or description provided to AI")
        return get_fallback_result()
    
    # Clean inputs
    title = title.strip()
    description = description.strip()
    
    if not title and not description:
        return get_fallback_result()

    # Enhanced prompt with Kenyan context
    prompt = f"""
You are an AI assistant for E-Mwananchi, a Kenyan citizen reporting platform. 
Analyze this report and classify it into the most appropriate county department.

CRITICAL: You MUST return ONLY valid JSON, no other text.

REPORT DETAILS:
Title: {title}
Description: {description}

AVAILABLE DEPARTMENTS: {json.dumps(known_departments, indent=2)}

ANALYSIS INSTRUCTIONS:
1. Determine if this is a legitimate citizen report (verified: true/false)
2. Calculate confidence score (0.0 to 1.0) based on clarity and relevance
3. Predict the most appropriate department from the available list
4. Suggest the likely Kenyan county if evident from the description

EXAMPLES OF GOOD CLASSIFICATION:
- "Potholes on Mombasa Road" → "Roads and Transport Department", confidence: 0.9
- "Garbage piling up in Kibera" → "Environment and Sanitation Department", confidence: 0.8
- "Street lights not working" → "Energy and Lighting Department", confidence: 0.7
- "Broken water pipe in residential area" → "Water and Sewerage Department", confidence: 0.85

RETURN STRICT JSON FORMAT:
{{
    "verified": true or false,
    "confidence": 0.0 to 1.0,
    "predicted_department": "Exact Department Name from Available List",
    "predicted_county": "County Name if evident, else null"
}}

IMPORTANT: 
- "verified" should be false only for spam, irrelevant, or incomprehensible reports
- "predicted_department" MUST be exactly from the available departments list
- Be specific and choose the most relevant department
- For Kenyan context, consider common county names: Nairobi, Mombasa, Kisumu, Nakuru, etc.
"""

    models_to_try = [
        "gemini-1.5-pro",
        "gemini-1.5-flash", 
        "gemini-1.0-pro"
    ]

    for model_name in models_to_try:
        try:
            logger.info(f"Attempting AI classification with {model_name}")
            
            # FIXED: Remove safety_settings parameter
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": 0.1,
                    "max_output_tokens": 500,
                }
            )
            
            raw_text = getattr(response, "text", "").strip()
            
            if not raw_text:
                logger.warning(f"No response from {model_name}")
                continue

            logger.info(f"Raw AI response from {model_name}: {raw_text}")
            
            # Extract JSON from response
            json_data = extract_json_from_text(raw_text)
            if json_data:
                processed_data = process_ai_response(json_data, known_departments)
                logger.info(f"AI classification successful: {processed_data}")
                return processed_data

        except Exception as e:
            logger.warning(f"AI model {model_name} failed: {str(e)}")
            if "UNAVAILABLE" in str(e) or "quota" in str(e).lower():
                time.sleep(2)
            continue

    logger.error("All AI models failed, using fallback")
    return get_fallback_result()

def extract_json_from_text(text: str):
    """Extract and validate JSON from AI response text."""
    try:
        # Try to find JSON pattern
        json_pattern = r'\{[^{}]*"[^"]*"[^{}]*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                # Validate it's proper JSON
                parsed = json.loads(match)
                return parsed
            except json.JSONDecodeError:
                continue
                
        # If pattern matching fails, try parsing the whole text
        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"JSON extraction failed: {e}")
        return None

def process_ai_response(data: dict, known_departments: list):
    """Process and validate AI response with proper error handling."""
    try:
        # Extract and validate fields with defaults
        verified = bool(data.get("verified", False))
        confidence = float(data.get("confidence", 0.0))
        predicted_department = data.get("predicted_department", "")
        predicted_county = data.get("predicted_county")
        
        # Validate confidence score range
        confidence = max(0.0, min(1.0, confidence))
        
        # Match department with available departments
        matched_department = match_department(predicted_department, known_departments)
        
        # Auto-verify based on confidence threshold
        confidence_threshold = 0.6
        if confidence >= confidence_threshold and matched_department:
            verified = True
        
        return {
            "verified": verified,
            "confidence": round(confidence, 2),  # Round to 2 decimal places
            "predicted_department": matched_department,
            "predicted_county": predicted_county,
        }
        
    except Exception as e:
        logger.error(f"AI response processing failed: {e}")
        return get_fallback_result()

def match_department(ai_department: str, known_departments: list):
    """Enhanced fuzzy match AI-predicted department with known departments."""
    if not ai_department or not known_departments:
        return None
    
    # Clean the department name
    ai_department_clean = ai_department.strip().lower()
    
    # Strategy 1: Exact match (case insensitive)
    for dept in known_departments:
        if dept and dept.lower() == ai_department_clean:
            return dept
    
    # Strategy 2: Contains match
    for dept in known_departments:
        if dept and (ai_department_clean in dept.lower() or dept.lower() in ai_department_clean):
            return dept
    
    # Strategy 3: Fuzzy matching with lower threshold
    try:
        best_match = process.extractOne(ai_department, known_departments, scorer=fuzz.token_sort_ratio)
        if best_match and best_match[1] > 60:  # Lowered threshold to 60%
            return best_match[0]
    except Exception as e:
        logger.warning(f"Fuzzy matching failed: {e}")
    
    # Strategy 4: Return the original if no match found
    return ai_department if ai_department else None

def get_fallback_result():
    """Return a safe fallback result when AI fails."""
    return {
        "verified": False,
        "confidence": 0.0,
        "predicted_department": None,
        "predicted_county": None,
    }