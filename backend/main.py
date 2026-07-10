from fastapi import FastAPI

app = FastAPI(title="TLCA Command Center")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello API"}
