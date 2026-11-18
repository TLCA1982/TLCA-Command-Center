const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const apiOrigin = 'https://api.example'
function load({ token='valid-token', tokenError, status=200 } = {}) {
  let calls=[]; let signInRequests=0
  let source=fs.readFileSync(path.join(__dirname,'../src/api.ts'),'utf8')
  source=source.replace('import.meta.env.VITE_API_BASE_URL',JSON.stringify(apiOrigin))
  const output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
  const exports={}
  vm.runInNewContext(output,{ exports, require:(name)=>{
    assert.equal(name,'./auth')
    return {getApiToken:async()=>{if(tokenError) throw tokenError;return token},requireSignIn:()=>signInRequests++}
  }, URL,Request,Headers, window:{location:{href:'https://site.example/',protocol:'https:',hostname:'site.example'}},fetch:async(input,options)=>{calls.push({input,options});return {status}} })
  return {api:exports,calls,signInRequests:()=>signInRequests}
}
test('API calls include the user token and preserve method/body',async()=>{
  const ctx=load()
  await ctx.api.apiFetch(apiOrigin+'/contacts',{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}})
  assert.equal(ctx.calls[0].options.headers.get('Authorization'),'Bearer valid-token')
  assert.equal(ctx.calls[0].options.headers.get('Content-Type'),'application/json')
  assert.equal(ctx.calls[0].options.credentials,'omit')
  assert.equal(ctx.calls[0].options.method,'POST')
  assert.equal(ctx.calls[0].options.body,'{}')
})
test('Token cannot be sent to a different origin',async()=>{
  const ctx=load();await assert.rejects(()=>ctx.api.apiFetch('https://other.example/contacts'));assert.equal(ctx.calls.length,0)
})
test('Missing login never sends a request',async()=>{
  const ctx=load({tokenError:new Error('Not signed in')});await assert.rejects(()=>ctx.api.apiFetch(apiOrigin+'/contacts'));assert.equal(ctx.calls.length,0)
})
test('Expired session requests login without retrying a write',async()=>{
  const ctx=load({status:401});await ctx.api.apiFetch(apiOrigin+'/contacts',{method:'POST'});assert.equal(ctx.signInRequests(),1);assert.equal(ctx.calls.length,1)
})
test('Forbidden user gets an explicit error',async()=>{
  const ctx=load({status:403});await assert.rejects(()=>ctx.api.apiFetch(apiOrigin+'/contacts'))
})
test('All application data requests use the authenticated API wrapper',()=>{
  function visit(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())visit(p);else if(p.endsWith('.tsx'))assert.doesNotMatch(fs.readFileSync(p,'utf8'),/\bfetch\s*\(/,p)}}
  visit(path.join(__dirname,'../src'))
})
