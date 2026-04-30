# Patched for grpcio 1.62 compatibility.
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import schema_pb2 as schema__pb2


class BenchmarkServiceStub(object):
    def __init__(self, channel):
        self.ProcessTransaction = channel.unary_unary(
            '/payload_gen.BenchmarkService/ProcessTransaction',
            request_serializer=schema__pb2.Transaction.SerializeToString,
            response_deserializer=schema__pb2.Transaction.FromString,
        )


class BenchmarkServiceServicer(object):
    def ProcessTransaction(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_BenchmarkServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
        'ProcessTransaction': grpc.unary_unary_rpc_method_handler(
            servicer.ProcessTransaction,
            request_deserializer=schema__pb2.Transaction.FromString,
            response_serializer=schema__pb2.Transaction.SerializeToString,
        ),
    }

    class _GenericHandler(grpc.GenericRpcHandler):
        def service_name(self):
            return 'payload_gen.BenchmarkService'

        def service(self, handler_call_details):
            # handler_call_details.method is the full path e.g.
            # "/payload_gen.BenchmarkService/ProcessTransaction"
            # Strip to just the method name for the dict lookup.
            method_name = handler_call_details.method.split('/')[-1]
            return rpc_method_handlers.get(method_name)

    server.add_generic_rpc_handlers((_GenericHandler(),))
