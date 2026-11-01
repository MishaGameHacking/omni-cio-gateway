/** Seal the existing AI-only key to the owner's temporary recipient. No HTTP. */
import {constants,createCipheriv,createHash,createPublicKey,publicEncrypt,randomBytes} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const PURPOSE='AnalystAI:Lenovo:TimewebGateway:v1', HOST='LAPTOP-NPSGA016';
export function sealCredential(recipient, token, now=Date.now()) {
  if(recipient?.schema_version!==1||recipient.purpose!==PURPOSE||recipient.host!==HOST||
    typeof recipient.public_key_pem!=='string'||recipient.public_key_pem.length>2000||
    !/^[a-f0-9]{64}$/.test(recipient.key_id??'')||
    createHash('sha256').update(recipient.public_key_pem).digest('hex')!==recipient.key_id||
    !Number.isFinite(Date.parse(recipient.expires_at_utc))||Date.parse(recipient.expires_at_utc)<=now||
    Date.parse(recipient.expires_at_utc)>now+2*60*60*1000) throw new Error('recipient_invalid_or_expired');
  if(typeof token!=='string'||!/^[A-Za-z0-9._~+/=-]{16,4096}$/.test(token)) throw new Error('gateway_credential_invalid');
  const publicKey=createPublicKey(recipient.public_key_pem);
  if(publicKey.asymmetricKeyType!=='rsa'||publicKey.asymmetricKeyDetails?.modulusLength!==3072) throw new Error('recipient_key_invalid');
  const session=randomBytes(32), nonce=randomBytes(12);
  const cipher=createCipheriv('aes-256-gcm',session,nonce);
  cipher.setAAD(Buffer.from(`${PURPOSE}:${HOST}:${recipient.key_id}`));
  const ciphertext=Buffer.concat([cipher.update(token,'ascii'),cipher.final(),cipher.getAuthTag()]);
  const wrapped=publicEncrypt({key:publicKey,padding:constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256',oaepLabel:Buffer.from(PURPOSE)},session);
  session.fill(0);
  return {schema_version:1,key_id:recipient.key_id,nonce:nonce.toString('base64'),
    wrapped_key:wrapped.toString('base64'),ciphertext:ciphertext.toString('base64')};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  try {
    const recipient=JSON.parse(await readFile(new URL('./fixtures/lenovo-gateway-recipient.json',import.meta.url),'utf8'));
    const run=process.env.GITHUB_RUN_ID??'';
    if(!/^[0-9]{1,20}$/.test(run)) throw new Error('workflow_identity_required');
    const sealed=sealCredential(recipient,process.env.TIMEWEB_AI_TOKEN??'');
    const data=JSON.stringify(sealed)+'\n';
    const destination=`C:/actions-runner-2/_work/_tool/analyst-evidence/timeweb-gateway-${run}.sealed.json`;
    await writeFile(destination,data,{flag:'wx',mode:0o600});
    console.log(JSON.stringify({sealed:true,key_id:recipient.key_id,sha256:createHash('sha256').update(data).digest('hex'),
      model_invocations:0,destination}));
  }catch {
    console.log(JSON.stringify({sealed:false,reason:'protected_delivery_failed'}));process.exitCode=2;
  }
}
