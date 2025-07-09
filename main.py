from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os, shutil, json
from dotenv import load_dotenv
from jinja2 import Template
import google.generativeai as genai
from parsers.flow_parser import parse_flow
from parsers.utils import extract_script

# Load API key from .env
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize FastAPI app
app = FastAPI()

# ✅ CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ In production, replace with your frontend URL (e.g. https://yourfrontend.onrender.com)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Save uploaded file
def save_file(upload: UploadFile):
    path = f"uploads/{upload.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path

# Main API Route
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
    job_description = json.load(open(job_desc_path))
    job_details = json.load(open(job_detail_path))

    job_data = {
        "company": job_description['recruitingContact']['company'],
        "terminal_address": job_description['recruitingContact']['terminalAddress'],
        "contract_type": job_description['recruitingContact']['jobCategory'],
        "time_zone": job_description['recruitingContact']['timeZone'],
        "job_ids": [str(j['jobId']) for j in job_description['recruitingContact']['jobType']],
        "job_titles": ", ".join(j['jobName'] for j in job_description['recruitingContact']['jobType']),
        "fleet": job_description['additionalInformation']['Miscellaneous']['Trucks(Can you describe your fleet in brief )'],
        "route_info": job_description['additionalInformation']['Driver Information']['Types of Routes'],
        "required_experience": job_description['additionalInformation']['Driver Information']['Minimum Required Experience for Drivers'],
        "schedule": job_description['additionalInformation']['Driver Schedule']['Work Schedules'],
        "start_time": job_description['additionalInformation']['Driver Schedule']['Start time for Driver'],
        "hours_per_day": job_description['additionalInformation']['Driver Schedule']['Typical hours run each day'],
        "miles_per_day": job_description['additionalInformation']['Driver Schedule']['Typical Miles Driven each day'],
        "stops_per_day": "150/day (extra $1 for additional stops)",
        "navigation": "Allowed",
        "weight_limit": "Up to 150 lbs (dolly provided)",
        "pay": job_description['additionalInformation']['Benefits']['How much do you Pay your drivers ?'],
        "pay_frequency": job_description['additionalInformation']['Benefits']['Payday'],
        "training": job_description['additionalInformation']['Benefits']['Training'],
        "overtime": "After 40 hrs/week",
        "benefits": [
            "Sick Leave: 3 days after 60 days",
            job_description['additionalInformation']['Benefits']['Other Benefits'],
            "Direct deposit: Yes"
        ],
        "screening_questions": [q['question'] for q in job_details.get("questionData", [])],
        "flow_steps": flow_steps,
        "script": example_script
    }

    # Load and render system prompt template
    with open("prompt_template.txt") as f:
        prompt_template = Template(f.read())
    rendered_prompt = prompt_template.render(**job_data)

    # Generate content using Gemini
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(rendered_prompt)

    # Save output
    os.makedirs("outputs", exist_ok=True)
    out_path = "outputs/final_prompt.txt"
    with open(out_path, "w") as f:
        f.write(response.text)

    return FileResponse(out_path, filename="RecruitAI_System_Prompt.txt", media_type="text/plain")
