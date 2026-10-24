
import os,sys,pathlib,subprocess,json,hashlib,base64,secrets,urllib.request,urllib.error
sys.path[:0]=["deploy","tools",".github/scripts"]
import prepare_owner_vm as p
from verify_cached_jdk import discover
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
CERT="bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
home=discover(os.environ.get("RUNNER_TOOL_CACHE",""))
source=pathlib.Path.home()/".android/debug.keystore"
assert source.is_file() and not source.is_symlink() and 256<=source.stat().st_size<=65536
certificate=subprocess.check_output([str(home/"bin/keytool.exe"),"-exportcert","-alias","androiddebugkey","-keystore",str(source),"-storepass","android"],stderr=subprocess.DEVNULL,timeout=30)
assert hashlib.sha256(certificate).hexdigest()==CERT,"original_signing_identity_mismatch"
recipient="-----BEGIN PUBLIC KEY-----\nMIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAx9N86UE38dAgc4IGWnvn\nDKGvIBC9dmQ0XEk9k8nPjJn/ml+teLhZsP+ygA6GbZKq+I2kfu80y4rU0vgtoAoA\nOsbqu1jJxJsN/nBmwaA+pbanaWTz85Yzo41iAEjAk68e6ZVMtqTuEO0s9pFzYgOa\n7E55Dt5uVphToYZbNPwoBEpDBP3NfUfYUcrfceVdk+0ST+eC62Ofef33aAh5jniu\n1i3nx1OckbOv/Y69y4RgH3jTRaODr/yuTTIvgMDU9RMio1mbfABk13ycpMiDiixD\nOJRgq6eGVJjXdRJQkCWdlIe7X0gNItXuc6Q9+IwXGbObTmtcSBXjYTM4uRuEP+38\nOI1cBQs+RJW0vPzUgOR8PAD0bicx1p2BxcVTbWdTNzJ+51O+kGOm7DcOqrAvWw80\nBhGmgTlf2DwLXsxkezrSgKl8XlH1rwGxvF0caP8docwSuYHpBMgfu4NnPeMVbERL\n/S4Kh2G8QEbw4D+aclq1J8ls2MzrMAJboPh9r3oi3/STAgMBAAE=\n-----END PUBLIC KEY-----\n".encode()
assert hashlib.sha256(recipient).hexdigest()=="e81bf61ed00ba4ec34b9961551869be49f71153b88b70383702b1209ec8ac22f"
public=serialization.load_pem_public_key(recipient)
assert public.key_size==3072
aad=("Analyst-AI-signing-restore:9415007:"+CERT+":"+hashlib.sha256(recipient).hexdigest()).encode()
aes=secrets.token_bytes(32);nonce=secrets.token_bytes(12)
encrypted_key=public.encrypt(aes,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=aad))
payload={"version":1,"server_id":9415007,"certificate_sha256":CERT,"recipient_sha256":hashlib.sha256(recipient).hexdigest(),"key":base64.b64encode(encrypted_key).decode(),"nonce":base64.b64encode(nonce).decode(),"ciphertext":base64.b64encode(AESGCM(aes).encrypt(nonce,source.read_bytes(),aad)).decode()}
raw=json.dumps(payload,separators=(",",":")).encode()
token=os.environ["GH_TOKEN"]
opener=urllib.request.build_opener(p.NoRedirect(),urllib.request.HTTPSHandler(context=p.verified_ssl_context()))
def github(method,url,body=None,content_type="application/json"):
    assert url.startswith(("https://api.github.com/repos/MishaGameHacking/omni-cio-gateway/","https://uploads.github.com/repos/MishaGameHacking/omni-cio-gateway/"))
    request=urllib.request.Request(url,method=method,data=body,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","Content-Type":content_type,"User-Agent":"analyst-timeweb-key-recovery"})
    with opener.open(request,timeout=60) as response:
        content=response.read(2097153);assert len(content)<=2097152
        return json.loads(content) if content else {}
base="https://api.github.com/repos/MishaGameHacking/omni-cio-gateway"
tag="private-timeweb-signing-9415007-"+os.environ["GITHUB_RUN_ID"]
assert not any(r["tag_name"]==tag for r in github("GET",base+"/releases?per_page=100")),"existing_handoff_reconcile"
release=github("POST",base+"/releases",json.dumps({"tag_name":tag,"target_commitish":os.environ["GITHUB_SHA"],"name":"Private encrypted Timeweb signing recovery","draft":True,"prerelease":True,"body":"Encrypted solely for the verified main Timeweb server; remove after successful restoration."}).encode())
assert release["draft"] is True and release["tag_name"]==tag
rid=release["id"]
asset=github("POST","https://uploads.github.com/repos/MishaGameHacking/omni-cio-gateway/releases/"+str(rid)+"/assets?name=analyst-9415007-signing.enc.json",raw,"application/octet-stream")
assert asset["size"]==len(raw) and asset["name"]=="analyst-9415007-signing.enc.json"
print("AMS_PRIVATE_SIGNING_HANDOFF="+json.dumps({"release_id":rid,"asset_id":asset["id"],"tag":tag,"ciphertext_sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"recipient_sha256":hashlib.sha256(recipient).hexdigest(),"certificate_sha256":CERT}),flush=True)
