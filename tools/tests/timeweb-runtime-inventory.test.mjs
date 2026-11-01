import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readCloud,summarizeInventory,inspectRuntime} from '../timeweb-runtime-inventory.mjs';

test('only explicit safe fields leave a cloud account response',()=>{
  const sensitive='do-not-export-this';
  const report=summarizeInventory({servers:[{id:123,name:'Analyst AI '+sensitive,ip:sensitive,
    root_pass:sensitive,ssh_keys:[sensitive],status:'on',ram:4096,cpu:2,disks:[{id:1,size:40,password:sensitive}]}]},
    {server_presets:[{id:1,cpu:2,ram:4096,price:800,password:sensitive}]},{servers_os:[{id:61,name:'ubuntu',version:'24.04',secret:sensitive}]});
  assert.equal(report.server_count,1);
  assert.equal(report.servers[0].matches_project_name,true);
  assert.equal(report.presets[0].price,800);
  assert.equal(report.operating_systems[0].os_name,'ubuntu');
  assert.ok(!JSON.stringify(report).includes(sensitive));
});
test('unrecognized inventory never becomes an empty account',()=>{
  assert.throws(()=>summarizeInventory({}, {presets:[]}, {os:[]}),/inventory_list_invalid/);
});
test('requests have no caller supplied path, method, or mutation route',()=>{
  assert.throws(()=>readCloud('/api/v1/servers','synthetic-key'),/inventory_route_or_credential_invalid/);
  assert.throws(()=>readCloud('servers','invalid\r\nkey'),/inventory_route_or_credential_invalid/);
});
test('transport errors are redacted and all three read requests are inspected',async()=>{
  const calls=[];
  const result=await inspectRuntime('synthetic-key',async(name)=>{
    calls.push(name);throw new Error('sensitive-provider-error');
  });
  assert.deepEqual(calls,['servers','presets','os']);
  assert.equal(result.status,'unavailable');
  assert.ok(!JSON.stringify(result).includes('sensitive-provider-error'));
});
