from typing import Union
from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


local_dir = "facebook1/bart-large-cnn"
model_local = AutoModelForSeq2SeqLM.from_pretrained(local_dir)
tokenizer_local = AutoTokenizer.from_pretrained(local_dir)

summarizer = pipeline(task="summarization", model=model_local,  tokenizer=tokenizer_local, device=0)

class SummarizationRequest(BaseModel):
    text: str


@app.get("/")
async def read_root():
    return "Hello World"


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.post("/summarize")
async def summarize(request: SummarizationRequest):
    try:
        summary = summarizer(request.text, max_length=150, min_length=40, do_sample=False)
        return {"summary": summary[0]["summary_text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
