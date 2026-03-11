import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

app = FastAPI(title="IndicTrans2 Translation Service")

MODEL_NAME = "ai4bharat/indictrans2-en-indic-1B"
tokenizer = None
model = None


def get_model():
    global tokenizer, model
    if tokenizer is not None and model is not None:
        return tokenizer, model
    try:
        hf_token = (os.getenv("HF_TOKEN", "") or "").strip() or None
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, token=hf_token)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, token=hf_token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model load failed: {exc}") from exc
    return tokenizer, model


class RequestModel(BaseModel):
    # Simple contract
    text: Optional[str] = None
    target_lang: Optional[str] = None

    # Batch contract
    sentences: Optional[List[str]] = None
    src_lang: Optional[str] = "eng_Latn"
    tgt_lang: Optional[str] = None


@app.get("/health")
def health():
    loaded = tokenizer is not None and model is not None
    return {"ok": True, "model": MODEL_NAME, "loaded": loaded}


@app.post("/translate")
def translate(req: RequestModel):
    tok, mdl = get_model()

    texts = req.sentences or ([] if not req.text else [req.text])
    if not texts:
        raise HTTPException(status_code=400, detail="Provide 'text' or 'sentences'.")

    target = (req.tgt_lang or req.target_lang or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Provide 'target_lang' or 'tgt_lang'.")

    target_id = tok.convert_tokens_to_ids(target)
    if target_id is None or target_id < 0:
        raise HTTPException(status_code=400, detail=f"Unsupported target_lang: {target}")

    outputs = []
    for item in texts:
        inputs = tok(str(item or ""), return_tensors="pt")
        generated = mdl.generate(
            **inputs,
            forced_bos_token_id=target_id,
            max_new_tokens=256,
        )
        out = tok.batch_decode(generated, skip_special_tokens=True)[0]
        outputs.append(out)

    return {
        "translated_text": outputs[0] if outputs else "",
        "translations": outputs,
        "src_lang": req.src_lang or "eng_Latn",
        "tgt_lang": target,
    }
