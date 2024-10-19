from fastapi import FastAPI, File, UploadFile, Form
from pydantic import BaseModel
from typing import List
from bs4 import BeautifulSoup
import pandas as pd
import os

app = FastAPI()

# Directory where CSV will be saved
DATA_DIR = './data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

class ColumnSelector(BaseModel):
    label: str
    selector: str

class FileUploadRequest(BaseModel):
    selectors: List[ColumnSelector]  # List of selectors with labels

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), selectors: List[ColumnSelector] = Form(...)):
    content = await file.read()

    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')

    # Extract data based on the provided selectors
    extracted_data = {}
    for column in selectors:
        # For each selector, extract text and store it under the label
        extracted_data[column.label] = [item.text.strip() for item in soup.select(column.selector)]

    # Ensure all columns have the same length by padding missing data
    max_len = max(len(v) for v in extracted_data.values())
    for key in extracted_data:
        extracted_data[key] += [''] * (max_len - len(extracted_data[key]))

    # Convert to DataFrame and save to CSV
    df = pd.DataFrame(extracted_data)
    csv_path = os.path.join(DATA_DIR, 'data.csv')
    df.to_csv(csv_path, index=False)

    return {"data": df.to_dict(orient='records')}

@app.get("/data/")
async def get_data():
    csv_path = os.path.join(DATA_DIR, 'data.csv')
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        return {"data": df.to_dict(orient='records')}
    return {"error": "No data found"}
