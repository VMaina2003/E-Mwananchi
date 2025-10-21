import os
import openai
from django.conf import settings

openai.api_key = settings.OPENAI_API_KEY

def classify_department_and_verification(title: str, description: str):
    prompt = f"""
You are a government service assistant.  
A citizen has submitted a report with title: "{title}" and description: "{description}".  
Decide which **department** should handle this ("Health", "Roads and Transport", "Environment and Water", "Education", "Housing and Urban Planning", "Trade and Industry", "ICT and Innovation", "Public Service and Administration").  
Also provide a **confidence score** between 0 and 1 (highest=most confident).  
Return a JSON object like:
{{ "department": "Roads and Transport", "confidence": 0.87 }}
"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You classify citizen reports into departments."},
                  {"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=60
    )
    content = response.choices[0].message.content.strip()
    try:
        result = eval(content)  # or better: json.loads
    except Exception:
        result = {"department": None, "confidence": 0.0}
    return result["department"], result["confidence"]
