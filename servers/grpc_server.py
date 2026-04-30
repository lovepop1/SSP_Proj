import grpc
import time
from concurrent import futures
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'payload_gen'))
import schema_pb2
import schema_pb2_grpc

class BenchmarkServiceServicer(schema_pb2_grpc.BenchmarkServiceServicer):
    def ProcessTransaction(self, request, context):
        # Return a distinct response object (not an echo) so request/response
        # wire sizes are independently measurable — required for Pillar 2.
        return schema_pb2.Transaction(
            transaction_id=request.transaction_id,
            timestamp=time.time(),
            user_id=0,
            amount=0.0,
            currency="OK",
            description="processed",
            merchant_code="SRV",
            metadata=""
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    schema_pb2_grpc.add_BenchmarkServiceServicer_to_server(BenchmarkServiceServicer(), server)
    server.add_insecure_port('0.0.0.0:50051')
    server.start()
    print("gRPC server listening on port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
