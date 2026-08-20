import pyotp
from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessAccept, AccessChallenge, AccessReject
import os

dict_path = os.path.join(os.path.dirname(__file__), "..", "radius", "dictionary")
srv = Client(server="127.0.0.1", secret=b"testing123", dict=Dictionary(dict_path))
srv.authport = 1812

req = srv.CreateAuthPacket(code=1, User_Name="demo")
req["User-Password"] = req.PwCrypt("demo")
reply = srv.SendPacket(req)
print("step1", reply.code, reply.get("Reply-Message"))
if reply.code != AccessChallenge:
    raise SystemExit("expected challenge")

code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
req2 = srv.CreateAuthPacket(code=1, User_Name="demo")
req2["User-Password"] = req2.PwCrypt(code)
req2["State"] = reply["State"][0]
reply2 = srv.SendPacket(req2)
print("step2", reply2.code, reply2.get("Reply-Message"), "otp", code)
if reply2.code != AccessAccept:
    raise SystemExit("expected accept")
print("OK")
