// 仅用于明确的本地隔离验收；不启动浏览器、不连接生产接口，不读取凭证。
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const publicRoot = path.join(root, 'apps/web/public');
const outputRoot = path.join(root, '.tmp/performance-main-baseline-20261103');
// 先核实固定真main基线已在本地；缺失时直接失败，不替换成其他版本。
const beforeHtml = execFileSync('git', ['show', '9c4318d2b9cafc4574e8d1b8558ffb6214f4e94e:apps/web/public/games/illusion-prototype/level4.html'], { cwd: root, maxBuffer: 2_000_000 });
const categories = [
  {slug:'puzzle',name:'解谜'}, {slug:'rts',name:'即时战略'}, {slug:'romance',name:'恋爱'},
].map((category, group) => ({ ...category, id:String(group+1),icon_url:null, projects:Array.from({length:6},(_,index)=>({
  id:String(group*10+index+1),slug:`performance-fixture-${group}-${index}`,name:`验收游戏 ${group}-${index}`,
  url:'https://game.invalid/',kind:'external',description:'仅限隔离验收数据',author_name:'验收作者',author_url:null,
  icon_url:'/uploads/cover-fixture/content',created_at:'2026-10-01T00:00:00Z',average_score:null,rating_count:0,rating_score_sum:0,view_count:12,my_score:null,
  ai_rating:group===0&&index===0?{score:7,label:'AI评分',assessment_id:'fixture-assessment',rule_version:'fixture-rule',weight_version:'fixture-weight',source_kind:'independent_ai',evaluated_at:'2026-10-30T00:00:00Z',reported_review_date:null,reported_timezone:null,game_version:null,dimensions:[{key:'playability',label:'可玩性',score:7,weight:1}],play_scope:{},limitations:[]}:null,
})) }));

function instrument(html, mode, variant) {
  const sha=crypto.createHash('sha256').update(html).digest('hex');
  const api=`
const qaRemembered=[];const qaReadout=document.createElement('pre');qaReadout.id='qa-readout';qaReadout.hidden=true;document.body.append(qaReadout);
const qaState=()=>({sourceHash:${JSON.stringify(sha)},mode:${JSON.stringify(mode)},point:[...state.player],input:state.input,route:state.route.length,won:state.won,endingReady:state.endingReady,failed,groups:Object.fromEntries(Object.entries(state.groups).map(([k,v])=>[k,{q:v.q,target:v.target}]))});
window.__releaseQa={
 configure(options={}){cancelAnimationFrame(animation);reset();cancelAnimationFrame(animation);if(options.groups)for(const[id,q]of Object.entries(options.groups))Object.assign(state.groups[id],{q,target:q});for(const[k,v]of Object.entries(options))if(k!=='groups'&&k!=='node')state[k]=v;if(options.node){state.player=nodePoint(ids[state.area][options.node]);state.frameId=defs[state.area].nodes[ids[state.area][options.node]].owner;state.location={node:ids[state.area][options.node]};}prototype.classList.toggle('is-inside',state.area==='inside');prototype.classList.toggle('is-ending',state.won);prototype.classList.toggle('is-complete',state.endingReady);result.hidden=!state.endingReady;document.getElementById('next-level').hidden=!state.endingReady;renderer.viewportFit=null;render();renderer.gl.finish();},
 capture(){render();renderer.gl.finish();const groups=new Map();for(const o of [...renderer.static,...renderer.dynamic]){if(o.visible===false)continue;if(!groups.has(o.kind))groups.set(o.kind,[]);groups.get(o.kind).push(o);}const packed=[];for(const[kind,objects]of groups){const expected=new Float32Array(objects.length*20);objects.forEach((o,i)=>{expected.set(o.matrix,i*20);expected.set(o.color,i*20+16);});const actual=new Float32Array(expected.length);renderer.gl.bindBuffer(renderer.gl.ARRAY_BUFFER,renderer.geometries[kind].instances);renderer.gl.getBufferSubData(renderer.gl.ARRAY_BUFFER,0,actual);for(let i=0;i<actual.length;i++)if(!Object.is(expected[i],actual[i]))throw Error('GPU instance mismatch '+kind+':'+i);packed.push({kind,count:objects.length,data:Array.from(actual)});}const serialize=o=>({kind:o.kind,matrix:Array.from(o.matrix),color:o.color,walk:o.walk,owner:o.owner,objectId:o.objectId,occludes:o.occludes,decorative:o.decorative});return{objects:[renderer.static.map(serialize),renderer.dynamic.map(serialize)],packed,pixels:canvas.toDataURL('image/png'),vp:Array.from(renderer.vp),glError:renderer.gl.getError()};}
};
let qaLast='';let qaCount=0;const qaTimer=setInterval(()=>{const item=qaState(),fingerprint=JSON.stringify(item);if(fingerprint!==qaLast){qaRemembered.push({...item,at:performance.now()});if(qaRemembered.length>100)qaRemembered.shift();qaLast=fingerprint;}qaReadout.textContent=JSON.stringify({...item,trace:qaRemembered,nodes:Object.entries(ids[state.area]).map(([name,id])=>({name,screen:renderer.project(nodePoint(id))}))});if(++qaCount>=2400)clearInterval(qaTimer);},250);
`;
  html=html.replace('    try{renderer=new Tiny3D(canvas);',api+'\n    try{renderer=new Tiny3D(canvas);');
  let after='';
  const common=`{P1:true,corner:1,bridgeAB:1,P2:true,P3:true,blockTurn:1,baseDrop:1,P4:true,bridgeBC:1}`;
  if(mode==='equivalence') after=`
setTimeout(async()=>{try{const c=${common};const cases=[['opening',{}],['A-turn',{groups:{stairs:1,A:1.4}}],['B-ready',{...c,zone:'B',groups:{stairs:1,A:4,pull:1,B:2.4},node:'arch-near',camera:[9.3,3.25,-.3]}],['C-turn',{...c,zone:'C',groups:{stairs:1,A:4,pull:1,B:4,C:.6,F:.35},node:'C-tip',camera:[19.8,8.7,-.7]}],['inside',{...c,area:'inside',zone:'C',node:'story',dialogue:{active:false,index:3,done:true},camera:[-1.2,3.2,-1.2]}],['goal',{...c,returned:true,zone:'C',player:[22.53,10.8,-1.7],frameId:'world',surfaceId:'goal-pedestal',camera:[19.8,8.7,-.7]}],['complete',{...c,returned:true,zone:'C',player:[22.2,10.8,-1.7],frameId:'world',surfaceId:'goal-pedestal',won:true,endingElapsed:2,endingReady:true,camera:[19.8,8.7,-.7]}],['reset',{}]];const results=[];for(const[name,options]of cases){__releaseQa.configure(options);results.push({name,snapshot:__releaseQa.capture()});}const response=await fetch('/__qa/result?name='+${JSON.stringify(variant)},{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'main-base-frozen-equivalence-no-timing',sourceHash:${JSON.stringify(sha)},viewport:[innerWidth,innerHeight,devicePixelRatio],results})});if(!response.ok)throw Error('Result save '+response.status);document.title='新main渲染等价完成 · '+${JSON.stringify(variant)};}catch(error){document.title='新main渲染等价失败';qaReadout.hidden=false;qaReadout.textContent=String(error);clearInterval(qaTimer);}},0);
`;
  if(mode==='goal') after=`
// 只在受控fixture暂停生命周期恢复，原输入门禁仍执行；开始后还原原rAF与pageshow。
const qaOriginalResume=resume;window.removeEventListener('pageshow',qaOriginalResume);resume=()=>{};
__releaseQa.configure({...${common},returned:true,zone:'C',groups:{stairs:1,A:4,pull:1,B:4,C:0,F:1},player:[22.53,10.8,-1.7],frameId:'world',surfaceId:'goal-pedestal',camera:[19.8,8.7,-.7]});checkProgress();render();renderer.gl.finish();
const qaStart=document.createElement('button');qaStart.id='qa-start';qaStart.textContent='恢复原rAF归中';qaStart.style.cssText='position:fixed;top:65px;right:20px;z-index:99';document.body.append(qaStart);qaStart.addEventListener('click',()=>{resume=qaOriginalResume;window.addEventListener('pageshow',resume);qaStart.remove();resume();},{once:true});document.title='新main近终点受控fixture';
`;
  if(after)html=html.replace('installDecor();reset();resume();}catch(error){fatal(error);}','installDecor();reset();resume();}catch(error){fatal(error);}\n'+after);
  return html;
}

http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://127.0.0.1:5197');
  if(url.pathname.startsWith('/api/')){
   if(!['GET','HEAD','OPTIONS'].includes(req.method)){res.writeHead(409,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{code:'LOCAL_QA_WRITE_BLOCKED'}}));return;}
   if(url.pathname.endsWith('/uploads/cover-fixture/content')){res.writeHead(200,{'Content-Type':'image/svg+xml'});res.end('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#315f4e"/></svg>');return;}
   res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify({data:url.pathname==='/api/v1/catalog'?{categories}:{settings:{}}}));return;
  }
  if(url.pathname==='/__qa/result'&&req.method==='POST'){
   const name=url.searchParams.get('name');if(!['before','after'].includes(name))throw Error('Unknown result');let body='';for await(const part of req){body+=part;if(body.length>16_000_000)throw Error('Result size limit');}JSON.parse(body);await fs.mkdir(outputRoot,{recursive:true});await fs.writeFile(path.join(outputRoot,`level4-${name}.json`),body);res.writeHead(204);res.end();return;
  }
  const file=path.resolve(publicRoot,'.'+decodeURIComponent(url.pathname));if(!file.startsWith(publicRoot+path.sep))throw Error('Outside public directory');let body=await fs.readFile(file);
  if(url.pathname.endsWith('/illusion-prototype/level4.html')){const variant=url.searchParams.get('variant')==='before'?'before':'after';if(variant==='before')body=beforeHtml;if(url.searchParams.has('qa'))body=Buffer.from(instrument(body.toString('utf8'),url.searchParams.get('qa'),variant));}
  const type={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml'}[path.extname(file)]||'application/octet-stream';res.writeHead(200,{'Content-Type':type,'Cache-Control':'no-store'});res.end(body);
 }catch(error){res.writeHead(404,{'Content-Type':'text/plain'});res.end(String(error));}
}).listen(5197,'127.0.0.1',()=>console.log('Release local isolated QA http://127.0.0.1:5197'));
