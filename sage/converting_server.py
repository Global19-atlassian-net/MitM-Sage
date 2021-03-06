import os
import socket
from six.moves import socketserver
import logging

from openmath.convert_pickle import PickleConverter as MitMConverter
from openmath import openmath as om

from scscp.client import TimeoutError, CONNECTED
from scscp.server import SCSCPServer
from scscp.scscp import SCSCPQuit, SCSCPProtocolError
from scscp import scscp

from scscp.socketserver import SCSCPServerRequestHandler, SCSCPSocketServer

import traceback

# improve sage openmath serialisation
# imported only for side-effects
import pickle_improvements

MitMBase = "http://opendreamkit.org/"
MitMCD = "scscp_transient_1"
MitMEval = "MitM_Evaluate"

class MitMRequestHandler(SCSCPServerRequestHandler):
    def __init__(self, converter, *args, **kwargs):
        self.converter = converter
        SCSCPServerRequestHandler.__init__(self, *args, **kwargs)
    
    def handle_call(self, call, head):
        if call.data.elem.cdbase == MitMBase and call.data.elem.cd == MitMCD and call.data.elem.name == MitMEval:
           # we take the one argument of MitMEval, import it (which triggers computation), and export it (i.e., the result of the computation)
           obj = call.data.arguments[0]
           try:
              objPy = self.converter.to_python(obj)
              return self.converter.to_openmath(objPy)
           except Exception as e:
              # we have to protect our error messages, the SCSCP server would swallow them
              eS = traceback.format_exc()
              return om.OMString(str(eS))
        return SCSCPServerRequestHandler.handle_call(self, call, head) # super does not work on this class in Python 2 

    def get_allowed_heads(self, data):
        return scscp.symbol_set([om.OMSymbol(base = MitMEval, cd = MitMCD, name = MitMEval)], cdnames=[MitMCD, 'scscp1'])
    
    def is_allowed_head(self, data):
        head = data.arguments[0]
        return conv.to_openmath((head.cdbase == MitMBase and head.cd == MitMCD and head.name == MitMEval)
                              or head.cd == 'scscp1')

    def get_service_description(self, data):
        return scscp.service_description(self.server.name.decode(),
                                             self.server.version.decode(),
                                             self.server.description)

class MitMSCSCPServer(SCSCPSocketServer):
    def __init__(self, openmath_converter, host='localhost', port=26136,
                     logger=None, name=b'MitM Server', version=b'none',
                     description='MitM SCSCP server'):
        
        # build a converter class
        class ReqHandler(MitMRequestHandler):
            def __init__(self, *args, **kwargs):
                MitMRequestHandler.__init__(self, openmath_converter, *args, **kwargs)
        
        SCSCPSocketServer.__init__(self, host=host, port=port, 
            logger=logger or logging.getLogger(__name__), name=name, version=version, 
            description=description, RequestHandlerClass=ReqHandler)

# fix to avoid coding large integers as strings
import copyreg
from sage.rings.integer import Integer
def pickle_sage_integer(i):
    return Integer, (int(i),)
copyreg.pickle(Integer, pickle_sage_integer)
    
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('demo_server')

    conv = MitMConverter()
    srv = MitMSCSCPServer(conv, host=os.environ.get('SCSCP_HOST') or 'localhost', logger=logger)
    
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        srv.server_close()

