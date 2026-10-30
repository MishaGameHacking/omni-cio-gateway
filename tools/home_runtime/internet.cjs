'use strict';
const crypto = require('node:crypto');
const cp = require('node:child_process');
const path = require('node:path');
const readline = require('node:readline');

module.exports = async ({github,context,core,side}) => {
  const label = 'Home HTTPS rehearsal '+context.runId+'-'+process.env.GITHUB_RUN_ATTEMPT;
  const repo = context.repo;
  async function publish(suffix, data) {
    const {data: row} = await github.rest.checks.create({...repo,name:label+' '+suffix,head_sha:context.sha,
      status:'completed',conclusion:'success',output:{title:'Disposable test coordination',summary:JSON.stringify(data)}});
    return row.id;
  }
  async function retire(id) {
    if(id) await github.rest.checks.update({...repo,check_run_id:id,output:{title:'Test closed',summary:'Ephemeral coordination complete.'}});
  }
  async function read(suffix,seconds) {
    const name=label+' '+suffix,deadline=Date.now()+seconds*1000;
    while(Date.now()<deadline){
      const {data}=await github.rest.checks.listForRef({...repo,ref:context.sha,check_name:name,per_page:20});
      const rows=data.check_runs.filter(x=>x.name===name&&x.head_sha===context.sha&&x.app?.slug==='github-actions'&&x.conclusion==='success');
      if(rows.length===1)return JSON.parse(rows[0].output.summary);
      if(rows.length>1)throw Error('Ambiguous test coordination');
      await new Promise(f=>setTimeout(f,3500));
    }
    throw Error('Coordination timed out');
  }
  async function home() {
    if(process.env.COMPUTERNAME!=='LAPTOP-NPSGA016')throw Error('Wrong home runner');
    const verifier=await read('recipient',320);
    const publicKey=crypto.createPublicKey({key:Buffer.from(verifier.pub,'base64'),format:'der',type:'spki'});
    if(publicKey.asymmetricKeyType!=='rsa'||publicKey.asymmetricKeyDetails.modulusLength<2048)throw Error('Invalid verifier key');
    const {data}=await github.rest.repos.getContent({...repo,path:'tools/home_runtime/ingress.py',ref:context.sha});
    const proc=cp.spawn(path.join(process.env.SystemRoot,'System32','wsl.exe'),['-d','AnalystAI-Home','-u','analyst-ai','--exec','/opt/analyst-ai/venv/bin/python','-I','-'],
      {windowsHide:true,stdio:['pipe','pipe','pipe']});
    proc.stdin.on('error',()=>{});proc.stderr.resume();proc.stdin.end(Buffer.from(data.content,'base64'));
    const done=new Promise(resolve=>{proc.on('error',()=>resolve(-1));proc.on('close',resolve);});
    let check,blocked;
    try{
      for await(const line of readline.createInterface({input:proc.stdout})){
        let d;try{d=JSON.parse(line);}catch{continue;}
        if(d.error){blocked=String(d.error).replace(/[^a-z0-9_]/gi,'').slice(0,80);continue;}
        if(check||typeof d.origin!=='string'||!/^https:\/\/[a-z0-9-]+\.trycloudflare\.com$/.test(d.origin))throw Error('Invalid rehearsal message');
        const key=crypto.randomBytes(32),iv=crypto.randomBytes(12),c=crypto.createCipheriv('aes-256-gcm',key,iv);
        const encrypted=Buffer.concat([c.update(JSON.stringify(d),'utf8'),c.final()]);
        check=await publish('sealed',{k:crypto.publicEncrypt({key:publicKey,oaepHash:'sha256'},key).toString('base64'),
          iv:iv.toString('base64'),tag:c.getAuthTag().toString('base64'),data:encrypted.toString('base64')});
      }
      const code=await done;
      if(code!==0||!check)throw Error('Home rehearsal stopped: '+(blocked||'process_failure'));
      core.info('HOME_HTTPS_ORIGIN='+JSON.stringify({closed:true,production_storage_used:false}));
    }finally{if(proc.exitCode===null)proc.kill();await retire(check);}
  }
  async function outside(){
    if(process.env.RUNNER_ENVIRONMENT!=='github-hosted')throw Error('Independent hosted runner required');
    const {publicKey,privateKey}=crypto.generateKeyPairSync('rsa',{modulusLength:2048});
    const id=await publish('recipient',{pub:publicKey.export({format:'der',type:'spki'}).toString('base64')});
    let origin,nonce;
    async function request(route,options={}){
      const r=await fetch(origin+route,{redirect:'error',signal:AbortSignal.timeout(10000),...options});
      const body=await r.text();if(body.length>24000)throw Error('Oversize HTTP reply');
      let json={};try{json=JSON.parse(body);}catch{}
      return {code:r.status,json};
    }
    try{
      const seal=await read('sealed',370);
      const key=crypto.privateDecrypt({key:privateKey,oaepHash:'sha256'},Buffer.from(seal.k,'base64'));
      const c=crypto.createDecipheriv('aes-256-gcm',key,Buffer.from(seal.iv,'base64'));c.setAuthTag(Buffer.from(seal.tag,'base64'));
      const d=JSON.parse(Buffer.concat([c.update(Buffer.from(seal.data,'base64')),c.final()]).toString());
      if(!/^https:\/\/[a-z0-9-]+\.trycloudflare\.com$/.test(d.origin)||!/^[a-f0-9]{36}$/.test(d.nonce))throw Error('Invalid test origin');
      origin=d.origin;nonce=d.nonce;
      let ok=false;
      for(let i=0;i<12&&!ok;i++){
        try{const r=await request('/probe/'+nonce);ok=r.code===200&&typeof r.json.proof==='string'&&
          crypto.createHash('sha256').update(r.json.proof).digest('hex')===d.proofHash;}catch{}
        if(!ok)await new Promise(f=>setTimeout(f,2500));
      }
      if(!ok)throw Error('Public HTTPS could not verify the home API challenge');
      const anonymous=await request('/me');
      const login=async password=>request('/auth/owner/login',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({password,device_name:'external-rehearsal'})});
      const grant=await login(d.password);
      if(anonymous.code!==401||grant.code!==200||typeof grant.json.access_token!=='string')throw Error('Public login boundary failed');
      const me=await request('/me',{headers:{Authorization:'Bearer '+grant.json.access_token}});
      const wrong=await login(crypto.randomBytes(24).toString('hex'));
      const blocked=await request('/tinvest/status');
      if(me.code!==200||String(me.json.telegram_id)!==d.subject||me.json.tinvest_connected!==false||wrong.code!==401||blocked.code!==404)
        throw Error('Public session check failed');
      core.info('HOME_HTTPS_VERIFIED='+JSON.stringify({external_tls:200,home_api_proof:true,anonymous:anonymous.code,
        password_login:grant.code,session:me.code,wrong_password:wrong.code,broker_route:blocked.code,production_accounts:0}));
    } finally {if(origin&&nonce){try{await request('/finish/'+nonce,{method:'POST'});}catch{}}await retire(id);}
  }
  return side==='home'?home():outside();
};
