import io
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pdf2image import convert_from_bytes
from pydantic import BaseModel, Field
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
from typing import List
from PIL import Image
import pytesseract # type: ignore

# Load API key from .env file
load_dotenv(dotenv_path="./.env")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

# Enable CORS for Next.js or other frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store
document_memory = {}
scheme_chat_memory = {"user": None, "schemes": [], "history": []}

# ------------------- Models -------------------

class UserInfo(BaseModel):
    age: int = Field(...)
    income: float = Field(...)
    veteran_status: bool = Field(...)
    disability_status: bool = Field(...)
    location: str = Field(...)
    employement_status: str = Field(...)

class Scheme(BaseModel):
    scheme_id: str
    name: str
    description: str
    eligibility_criteria: str

class SchemeChatRequest(BaseModel):
    question: str

class ChatRequest(BaseModel):
    question: str

class EmotionRequest(BaseModel):
    text: str

# ------------------- Utility Functions -------------------

#Schemes

def is_json(my_str):
    try:
        json_object = json.loads(my_str)
        return True
    except:
        return False
async def get_recommendations(user_info: dict, schemes: list) -> dict:
    prompt = """
You are an assistant that helps elderly citizens in the U.S. discover personalized benefits according to the state in which they reside.

Given the user's personal details, provide:
1. A list of **government schemes** they are **specifically eligible for**.
2. A list of **discounts or offers** on **merchandise, groceries, or restaurants** that apply to them.

Strictly return your response in the following JSON format and do not include any other explanation or formatting:
{
  "state": "<User's state>",
  "gov_schemes": [{"name": "...", "description": "...", "link": "..."}],
  "discounts": [{"name": "...", "description": "...", "link": "..."}]
}
Limit the response to 500 words.
"""
    for key, value in user_info.items():
        prompt += f"- {key}: {value}\n"
    for s in schemes:
        prompt += f"- {s['name']}: {s['description']}\n"

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")  # ? match your version
        response = model.generate_content(prompt)
        content = response.text.strip()

        print("\n[Gemini RAW OUTPUT]\n", content)  # ? For debugging

        if is_json(content):
            return json.loads(content)
        else:
            return {"raw_text": content}  # fallback so app doesn't break

    except Exception as e:
        print("[Gemini ERROR]", str(e))
        import traceback
        traceback.print_exc()
        return {"error": "Failed to fetch recommendations."}

def chat_about_schemes(question, user_data, schemes, history):
    try:
        prompt = "You are a helpful assistant helping elderly citizens.Limit the ans to just 2 short impresive sentences.You must only chat about the schemes above and other schemes related request.If users ask any other qns just response to user  that we can only chat regarding the schemes. \n"
        for key, value in user_data.items():
            prompt += f"- {key}: {value}\n"
        for s in schemes:
            prompt += f"- {s['name']}: {s['description']}\n"
        for role, message in history:
            prompt += f"{role}: {message}\n"
        prompt += f"User: {question}\nAI:"
        model = genai.GenerativeModel("gemini-1.5-pro")
        return model.generate_content(prompt).text
    except Exception as e:
        print("[Scheme Chat ERROR]", str(e))
        return "An error occurred during the scheme chat."

def load_schemes():
    return [
        {
            "scheme_id": "SC001",
            "name": "Senior Medicare Plan",
            "description": "Health coverage for seniors above 65.",
            "eligibility_criteria": "Age > 65, Income < $2000"
        },
        # Add more schemes as needed
    ]

#Insurance

def extract_text_from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "".join(page.get_text() for page in doc).strip()

def summarize_text(text):
    try:
        prompt = f"Summarize this insurance document in plain English.Just give main and important points.Limit words count to 300.If you detect any other other content than insurance dont further give suggestions just give that this is not insurance doc give another doc.:\n\n{text}"
        model = genai.GenerativeModel("gemini-1.5-pro")

        return model.generate_content(prompt).text
    except Exception as e:
        print("[Gemini ERROR]", str(e))
        return "An error occurred while summarizing."

def chat_with_context(question, doc_text, history):
    try:
        prompt = f"You are an insurance agent and you are going to chat with the user regarding their insurance they have uploaded.You should chat only about insurance related doubts, if you encountered any other quires just dont chat reply plz chat about insurance related content.Limit response to 2 sentences:\n{doc_text}\n\n"
        for role, message in history:
            prompt += f"{role}: {message}\n"
        prompt += f"User: {question}\nAI:"
        model = genai.GenerativeModel("gemini-1.5-pro")

        return model.generate_content(prompt).text
    except Exception as e:
        print("[Chat ERROR]", str(e))
        return "An error occurred during chat."
    
#Prescription

def analyze_prescription_text(text):
    try:
        prompt = f"""
        Analyze the following prescription content and return a list of medicines with:
        - medicine name
        - one-line description about the medicine , why we take it 
        - when to take. just when to take eg:Before breakfast,after lunch, etc.
        - instructions in one sentences about how to consume the medicine properly.

        Prescription:
{text}

        Format:
        [
          {{"medicine": "...", "description": "...", "timing": "...", "instructions": "..."}},
          ...
        ]
        """
        model = genai.GenerativeModel("gemini-1.5-pro")

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("[Prescription ERROR]", str(e))
        return "An error occurred during prescription analysis."
    
def extract_text_from_image_bytes(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")  # Convert to grayscale
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, config=custom_config)
        return text.strip()
    except Exception as e:
        print("[OCR ERROR]", e)
        return ""


def extract_text_from_pdf_with_fallback(file_bytes):
    text = extract_text_from_pdf(file_bytes)
    if not text:  # fallback to image extraction
        images = convert_from_bytes(file_bytes)
        all_text = ""
        for img in images:
            all_text += pytesseract.image_to_string(img)
        return all_text.strip()
    return text


#Journal   
def analyze_reflection(text):
    try:
        prompt = f"""
        Analyze this reflection and return:
        - An interesting and creative title
        - 3 emotional keywords
        - A short summary.Limit to 100 words.

        Text:
{text}

        Format:
        {{"title": "...", "emotional_keywords": ["..."], "summary": "..."}}
        """
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("[Reflection ERROR]", str(e))
        return "An error occurred while analyzing reflection."



# ------------------- Routes -------------------

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Welcome to Insurance API"}

#Schemes
@app.post("/recommend", tags=["Schemes"])
async def recommend_schemes(user: UserInfo):
    user_dict = user.model_dump()
    schemes = load_schemes()
    scheme_chat_memory.update({"user": user_dict, "schemes": schemes, "history": []})
    return {"recommendation": await get_recommendations(user_dict, schemes)}

@app.post("/chat-schemes", tags=["Schemes"])
def chat_schemes(req: SchemeChatRequest):
    if not scheme_chat_memory["user"] or not scheme_chat_memory["schemes"]:
        return {"error": "No user data or schemes. Call /recommend first."}
    history = scheme_chat_memory["history"]
    question = req.question
    history.append(("User", question))
    answer = chat_about_schemes(question, scheme_chat_memory["user"], scheme_chat_memory["schemes"], history)
    history.append(("AI", answer))
    return {"answer": answer}

#Insurances
@app.post("/upload", tags=["Insurance"])
async def upload_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        text = extract_text_from_pdf(contents)
        if not text:
            return {"error": "Could not extract text."}
        summary = summarize_text(text)
        document_memory.update({"text": text, "history": []})
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}

@app.post("/chat", tags=["Insurance"])
def chat(req: ChatRequest):
    if "text" not in document_memory:
        return {"error": "No document uploaded."}
    history = document_memory["history"]
    history.append(("User", req.question))
    answer = chat_with_context(req.question, document_memory["text"], history)
    history.append(("AI", answer))
    return {"answer": answer}

#Prescription

@app.post("/analyze-prescription", tags=["Pres"])
async def analyze_prescription(file: UploadFile = File(...)):
    try:
        content = await file.read()

        # Step 1: Extract text (either from image or fallback from pdf)
        if file.content_type == "application/pdf":
            from pdf2image import convert_from_bytes
            text = extract_text_from_pdf_with_fallback(content)
        else:
            text = extract_text_from_image_bytes(content)

        if not text:
            return {"error": "Could not extract any text from the file."}

        # Step 2: Analyze using Gemini
        result = analyze_prescription_text(text)
        return {"medications": result}

    except Exception as e:
        return {"error": str(e)}
    
#Journal

@app.post("/analyze-emotion", tags=["Journal"])
def analyze_reflection_route(req: EmotionRequest):
    return {"analysis": analyze_reflection(req.text)}
