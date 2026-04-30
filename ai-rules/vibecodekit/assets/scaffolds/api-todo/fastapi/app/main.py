from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="VibecodeKit Todo API")


class NewTodo(BaseModel):
    title: str
    done: bool = False


class Todo(NewTodo):
    id: int


_DB: dict[int, Todo] = {}
_NEXT_ID = 1


@app.get("/todos", response_model=list[Todo])
def list_todos():
    return list(_DB.values())


@app.post("/todos", response_model=Todo, status_code=201)
def create(t: NewTodo):
    global _NEXT_ID
    todo = Todo(id=_NEXT_ID, **t.model_dump())
    _DB[_NEXT_ID] = todo
    _NEXT_ID += 1
    return todo


@app.delete("/todos/{tid}", status_code=204)
def delete(tid: int):
    if tid not in _DB:
        raise HTTPException(404)
    _DB.pop(tid)
