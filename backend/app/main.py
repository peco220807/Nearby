from fastapi import FastAPI

app = FastAPI(title="Nearby API")


@app.get("/health")
def health():
    return {"status": "ok"}