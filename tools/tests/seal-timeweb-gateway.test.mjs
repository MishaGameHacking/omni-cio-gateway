import {strict as assert} from 'node:assert';
import {constants,createDecipheriv,createHash,generateKeyPairSync,privateDecrypt} from 'node:crypto';
import test from 'node:test';
import {sealCredential} from '../seal-timeweb-gateway.mjs';

test('credential roundtrip is recipient-bound and plaintext is absent from the envelope',()=>{
  const {privateKey,publicKey}=generateKeyPairSync('rsa',{modulusLength:3072});
  const pem=publicKey.export({type:'spki',format:'pem'});
  const now=Date.now();
  const recipient={schema_version:1,purpose:'AnalystAI:Lenovo:TimewebGateway:v1',host:'LAPTOP-NPSGA016',
    public_key_pem:pem,key_id:createHash('sha256').update(pem).digest('hex'),expires_at_utc:new Date(now+60000).toISOString()};
  const token='synthetic-credential-not-a-real-token';
  const envelope=sealCredential(recipient,token,now);
  assert.equal(JSON.stringify(envelope).includes(token),false);
  const session=privateDecrypt({key:privateKey,padding:constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256',
    oaepLabel:Buffer.from(recipient.purpose)},Buffer.from(envelope.wrapped_key,'base64'));
  const raw=Buffer.from(envelope.ciphertext,'base64');
  const decrypt=createDecipheriv('aes-256-gcm',session,Buffer.from(envelope.nonce,'base64'));
  decrypt.setAAD(Buffer.from(`${recipient.purpose}:${recipient.host}:${recipient.key_id}`));
  decrypt.setAuthTag(raw.subarray(-16));
  assert.equal(Buffer.concat([decrypt.update(raw.subarray(0,-16)),decrypt.final()]).toString(),token);
  for(const replacement of [{host:'different-host'},{purpose:'different-purpose'},{key_id:'0'.repeat(64)},
    {expires_at_utc:new Date(now-1).toISOString()}]) assert.throws(()=>sealCredential({...recipient,...replacement},token,now));
  assert.throws(()=>sealCredential(recipient,'secret\nheader: injected',now));
});
