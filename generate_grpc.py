import subprocess
import sys
import os

def generate_grpc_files():
    """Generate gRPC Python files from proto file"""
    try:
        # Use the current python interpreter
        python_executable = sys.executable
        
        # Generate gRPC files
        result = subprocess.run([
            python_executable, "-m", "grpc_tools.protoc",
            "-I.", "--python_out=.", "--grpc_python_out=.",
            "transaction.proto"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ gRPC files generated successfully")
            print("Generated: transaction_pb2.py and transaction_pb2_grpc.py")
        else:
            print("❌ Error generating gRPC files:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    generate_grpc_files()
