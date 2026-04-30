from fastapi import FastAPI, HTTPException

from .models import Contact, NewContact

app = FastAPI(title="VibecodeKit CRM API")
_DB: list[Contact] = []
_NEXT_ID = 1


@app.get("/contacts", response_model=list[Contact])
def list_contacts():
    return _DB


@app.post("/contacts", response_model=Contact, status_code=201)
def create_contact(payload: NewContact):
    global _NEXT_ID
    c = Contact(id=_NEXT_ID, **payload.model_dump())
    _DB.append(c)
    _NEXT_ID += 1
    return c


@app.get("/contacts/{cid}", response_model=Contact)
def get_contact(cid: int):
    for c in _DB:
        if c.id == cid:
            return c
    raise HTTPException(status_code=404, detail="not found")
