from fastapi import FastAPI
from pydantic import BaseModel
import json
import time
from payload_generator import generate_10kb_payload

app = FastAPI()

class Transaction(BaseModel):
    transaction_id: int
    timestamp: str
    user_id: str
    event_type: str
    amount: float
    padding: str

class TransactionResponse(BaseModel):
    success: bool
    message: str
    processing_time_ms: int

@app.post("/api/transaction")
async def process_transaction(transaction: Transaction):
    start_time = time.perf_counter()
    
    # Simulate minimal processing
    processed_data = {
        "transaction_id": transaction.transaction_id,
        "status": "processed",
        "timestamp": transaction.timestamp
    }
    
    end_time = time.perf_counter()
    processing_time_ms = int((end_time - start_time) * 1000)
    
    return TransactionResponse(
        success=True,
        message="Transaction processed successfully",
        processing_time_ms=processing_time_ms
    )

@app.get("/api/payload")
async def get_payload():
    """Endpoint to get sample 10KB payload for testing"""
    return generate_10kb_payload()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
