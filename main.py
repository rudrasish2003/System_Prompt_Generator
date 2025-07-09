from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os, shutil, json
from dotenv import load_dotenv
from jinja2 import Template
import google.generativeai as genai
from parsers.flow_parser import parse_flow
from parsers.utils import extract_script

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use your frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def save_file(upload: UploadFile):
    path = f"uploads/{upload.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path

@app.post("/generate/")
async def generate(
    flow_file: UploadFile = File(...),
    example_file: UploadFile = File(...),
    job_desc_file: UploadFile = File(...),
    job_detail_file: UploadFile = File(...)
):
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

    job_data = {
        "company": recruiting.get('company', None),
        "terminal_address": recruiting.get('terminalAddress', None),
        "contract_type": recruiting.get('jobCategory', None),
        "time_zone": recruiting.get('timeZone', None),
        "job_ids": [str(j.get('jobId')) for j in recruiting.get('jobType', [])],
        "job_titles": ", ".join(j.get('jobName', '') for j in recruiting.get('jobType', [])),
        "fleet": additional.get('Miscellaneous', {}).get('Trucks(Can you describe your fleet in brief )', None),
        "route_info": additional.get('Driver Information', {}).get('Types of Routes', None),
        "required_experience": additional.get('Driver Information', {}).get('Minimum Required Experience for Drivers', None),
        "schedule": additional.get('Driver Schedule', {}).get('Work Schedules', None),
        "start_time": additional.get('Driver Schedule', {}).get('Start time for Driver', None),
        "hours_per_day": additional.get('Driver Schedule', {}).get('Typical hours run each day', None),
        "miles_per_day": additional.get('Driver Schedule', {}).get('Typical Miles Driven each day', None),
        "stops_per_day": "150/day (extra $1 for additional stops)",
        "navigation": "Allowed",
        "weight_limit": "Up to 150 lbs (dolly provided)",
        "pay": additional.get('Benefits', {}).get('How much do you Pay your drivers ?', None),
        "pay_frequency": additional.get('Benefits', {}).get('Payday', None),
        "training": additional.get('Benefits', {}).get('Training', None),
        "overtime": "After 40 hrs/week",
        "benefits": [
            "Sick Leave: 3 days after 60 days",
            additional.get('Benefits', {}).get('Other Benefits', None),
            "Direct deposit: Yes"
        ],
        "screening_questions": [q.get('question', '') for q in job_details.get("questionData", [])],
        "flow_steps": flow_steps,
        "script": example_script
    }

    # Render template
    with open("prompt_template.txt") as f:
        prompt_template = Template(f.read())
    rendered_prompt = prompt_template.render(**job_data)

    # Send to Gemini
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(rendered_prompt)

    # Save output
    os.makedirs("outputs", exist_ok=True)
    out_path = "outputs/final_prompt.txt"
    with open(out_path, "w") as f:
        f.write(response.text)

    return FileResponse(out_path, filename="RecruitAI_System_Prompt.txt", media_type="text/plain")
