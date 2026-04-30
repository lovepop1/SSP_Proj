from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

app = FastAPI()

# Disable uvicorn access logging for accurate benchmarking
# Otherwise writing to stdout heavily impacts RPS (Requests Per Second)
log = logging.getLogger("uvicorn.access")
log.disabled = True

@app.post("/transaction")
async def handle_transaction(request: Request):
    # Simulate realistic framework behavior by decoding the payload
    # which introduces the User-Space JSON serialization cost
    payload = await request.json()
    
    # In a real app we'd validate here, but this is pure serialization overhead test
    return JSONResponse(content=payload)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, access_log=False)
