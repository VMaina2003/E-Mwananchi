# import re
# import json
# from decouple import config
# from openai import OpenAI

# # ✅ Load the API key from .env using python-decouple (not os.getenv)
# client = OpenAI(api_key=config("OPENAI_API_KEY"))

# def classify_department(title: str, description: str):
#     """
#     Uses GPT to:
#     - Verify if the report is genuine.
#     - Predict the most appropriate department.
#     - Predict the most likely county.
#     - Return a confidence score.
#     """
#     prompt = f"""
#     You are an AI assistant for a Kenyan citizen–government platform called E-Mwananchi.
#     Analyze the following citizen report and determine:

#     1. Whether it describes a genuine public issue. (true/false)
#     2. Which department should handle it.
#     3. Which Kenyan county is most likely involved.
#     4. A confidence score between 0 and 1.

#     Departments:
#     - Health
#     - Education
#     - Roads and Transport
#     - Environment and Water
#     - Trade and Industry
#     - ICT and Innovation
#     - Agriculture, Livestock and Fisheries
#     - Housing and Urban Planning
#     - Finance and Economic Planning
#     - Public Service and Administration

#     Respond strictly in valid JSON format as shown below:
#     {{
#         "verified": true or false,
#         "confidence": 0.0 to 1.0,
#         "predicted_department": "Department Name",
#         "predicted_county": "County Name"
#     }}

#     Report Title: {title}
#     Description: {description}
#     """

#     try:
#         # Send prompt to OpenAI
#         response = client.chat.completions.create(
#             model="gpt-4o",  # gpt-4o is more reliable than mini
#             messages=[
#                 {"role": "system", "content": "You are a precise and factual civic report classifier."},
#                 {"role": "user", "content": prompt},
#             ],
#             temperature=0.0,
#             max_tokens=250,
#         )

#         raw_output = response.choices[0].message.content.strip()
#         print("AI Response:", raw_output)

#         # Try to extract JSON safely
#         try:
#             json_str = re.search(r'\{.*\}', raw_output, re.DOTALL).group()
#             return json.loads(json_str)
#         except Exception:
#             print("Could not parse valid JSON:", raw_output)
#             return {
#                 "verified": False,
#                 "confidence": 0.0,
#                 "predicted_department": None,
#                 "predicted_county": None,
#             }

#     except Exception as e:
#         print("AI classification error:", e)
#         return {
#             "verified": False,
#             "confidence": 0.0,
#             "predicted_department": None,
#             "predicted_county": None,
#         }

import os
import json
import re
import google.generativeai as genai
from django.conf import settings

# Configure Gemini client
genai.configure(api_key=settings.GEMINI_API_KEY)

def classify_department(title: str, description: str):
    """
    Uses Gemini to:
    - Verify if the report is genuine.
    - Predict the appropriate department.
    - Predict the likely county.
    - Return a confidence score.
    """
    prompt = f"""
    You are an AI assistant for a Kenyan citizen–government platform called E-Mwananchi.
    Analyze the following citizen report and determine:

    1. Whether it describes a genuine public issue (true/false).
    2. Which department should handle it.
    3. Which Kenyan county is most likely involved.
    4. Provide a confidence score between 0 and 1.

    Departments:
    - Health
    - Education
    - Roads and Transport
    - Environment and Water
    - Trade and Industry
    - ICT and Innovation
    - Agriculture, Livestock and Fisheries
    - Housing and Urban Planning
    - Finance and Economic Planning
    - Public Service and Administration

    Respond strictly in valid JSON format:
    {{
        "verified": true or false,
        "confidence": 0.0 to 1.0,
        "predicted_department": "Department Name",
        "predicted_county": "County Name"
    }}

    Report Title: {title}
    Description: {description}
    """

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        raw_output = response.text.strip()
        print("Gemini Response:", raw_output)

        # Extract JSON from output
        json_str = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if json_str:
            return json.loads(json_str.group())

        print("Could not parse JSON:", raw_output)
        return {
            "verified": False,
            "confidence": 0.0,
            "predicted_department": None,
            "predicted_county": None,
        }

    except Exception as e:
        print("Gemini classification error:", e)
        return {
            "verified": False,
            "confidence": 0.0,
            "predicted_department": None,
            "predicted_county": None,
        }

