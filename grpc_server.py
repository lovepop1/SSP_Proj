import grpc
import time
from concurrent import futures
import transaction_pb2
import transaction_pb2_grpc
from payload_generator import generate_10kb_payload

class TransactionServiceImpl(transaction_pb2_grpc.TransactionServiceServicer):
    
    def ProcessTransaction(self, request, context):
        start_time = time.perf_counter()
        
        # Simulate minimal processing
        processed_data = {
            "transaction_id": request.transaction_id,
            "status": "processed",
            "timestamp": request.timestamp
        }
        
        end_time = time.perf_counter()
        processing_time_ms = int((end_time - start_time) * 1000)
        
        return transaction_pb2.TransactionResponse(
            success=True,
            message="Transaction processed successfully",
            processing_time_ms=processing_time_ms
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=32))
    transaction_pb2_grpc.add_TransactionServiceServicer_to_server(
        TransactionServiceImpl(), server
    )
    
    server.add_insecure_port('[::]:50051')
    server.start()
    print("🚀 gRPC server started on port 50051")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
