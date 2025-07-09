from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os, shutil, json
from dotenv import load_dotenv
from jinja2 import Template
import google.generativeai as genai
from parsers.flow_parser import parse_flow
from parsers.utils import extract_script

# Load Gemini API key from .env
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

# ✅ CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to your frontend domain in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Helper: fallback for missing values
def safe_get(value, default="Not provided"):
    if isinstance(value, str):
        value = value.strip()
    return value if value not in [None, "", "null"] else default

# ✅ Save file to /uploads
def save_file(upload: UploadFile):
    path = f"uploads/{upload.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path

# ✅ Main API
@app.post("/generate/")
async def generate(
    flow_file: UploadFile = File(...),
    example_file: UploadFile = File(...),
    job_desc_file: UploadFile = File(...),
    job_detail_file: UploadFile = File(...)
):
    # Save uploaded files
    flow_path = save_file(flow_file)
    example_path = save_file(example_file)
    job_desc_path = save_file(job_desc_file)
    job_detail_path = save_file(job_detail_file)

    # Parse inputs
    flow_steps = parse_flow(flow_path)
    example_script = extract_script(example_path)

    try:
        job_description = json.load(open(job_desc_path))
    except Exception:
        return {"error": "Invalid job description JSON"}

    try:
        job_details = json.load(open(job_detail_path))
    except Exception:
        return {"error": "Invalid job detail JSON"}

    recruiting = job_description.get('recruitingContact', {})
    additional = job_description.get('additionalInformation', {})

    # ✅ Build job data with safe_get
    job_data = {
        "company": safe_get(recruiting.get('company')),
        "terminal_address": safe_get(recruiting.get('terminalAddress')),
        "contract_type": safe_get(recruiting.get('jobCategory')),
        "time_zone": safe_get(recruiting.get('timeZone')),
        "job_ids": [str(j.get('jobId')) for j in recruiting.get('jobType', [])],
        "job_titles": ", ".join(safe_get(j.get('jobName')) for j in recruiting.get('jobType', [])),
        "fleet": safe_get(additional.get('Miscellaneous', {}).get('Trucks(Can you describe your fleet in brief )')),
        "route_info": safe_get(additional.get('Driver Information', {}).get('Types of Routes')),
        "required_experience": safe_get(additional.get('Driver Information', {}).get('Minimum Required Experience for Drivers')),
        "schedule": safe_get(additional.get('Driver Schedule', {}).get('Work Schedules')),
        "start_time": safe_get(additional.get('Driver Schedule', {}).get('Start time for Driver')),
        "hours_per_day": safe_get(additional.get('Driver Schedule', {}).get('Typical hours run each day')),
        "miles_per_day": safe_get(additional.get('Driver Schedule', {}).get('Typical Miles Driven each day')),
        "stops_per_day": "150/day (extra $1 for additional stops)",
        "navigation": "Allowed",
        "weight_limit": "Up to 150 lbs (dolly provided)",
        "pay": safe_get(additional.get('Benefits', {}).get('How much do you Pay your drivers ?')),
        "pay_frequency": safe_get(additional.get('Benefits', {}).get('Payday')),
        "training": safe_get(additional.get('Benefits', {}).get('Training')),
        "overtime": "After 40 hrs/week",
        "benefits": [
            "Sick Leave: 3 days after 60 days",
            safe_get(additional.get('Benefits', {}).get('Other Benefits')),
            "Direct deposit: Yes"
        ],
        "screening_questions": [safe_get(q.get('question')) for q in job_details.get("questionData", [])],
        "flow_steps": flow_steps,
        "script": example_script
    }

    # ✅ Render Jinja template
    with open("prompt_template.txt") as f:
        prompt_template = Template(f.read())
    rendered_prompt = prompt_template.render(**job_data)

    # ✅ Send to Gemini 1.5 Flash
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(rendered_prompt)

    # ✅ Clean Gemini output (remove \n, \\\n, etc.)
    output_text = response.text.replace("\\n", "\n").replace("\n\n", "\n").strip()

    # ✅ Save to file
    os.makedirs("outputs", exist_ok=True)
    out_path = "outputs/final_prompt.txt"
    with open(out_path, "w") as f:
        f.write(output_text)

    return FileResponse(out_path, filename="RecruitAI_System_Prompt.txt", media_type="text/plain")
