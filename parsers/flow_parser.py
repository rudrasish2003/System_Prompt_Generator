import xml.etree.ElementTree as ET
from PIL import Image
import pytesseract

def parse_flow(path):
    if path.endswith(".xml"):
        tree = ET.parse(path)
        return [step.text.strip() for step in tree.iter("step") if step.text]
    elif path.endswith(".png") or path.endswith(".jpg"):
        text = pytesseract.image_to_string(Image.open(path))
        return [line.strip() for line in text.split("\n") if line.strip()]
    else:
        return ["Unsupported file format"]
