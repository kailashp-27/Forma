const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
const React=require('react');
const {renderToString}=require('react-dom/server');
const root=path.resolve(__dirname,'../src');
function source(name,cache={}){if(cache[name])return cache[name];const filename=path.join(root,name+'.ts'),js=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const module={exports:{}};new Function('require','module','exports',js)(id=>id==='react'&&cache.__react?cache.__react:id.startsWith('./')?source(id.slice(2),cache):require(id),module,module.exports);return cache[name]=module.exports;}
const {replayTimeline,replayFrameAt}=source('replay');
const {CameraMeasurements,compareObservation}=source('performance');
test('camera measurements include encoding and transport, with correct tracking coverage',()=>{
 const m=new CameraMeasurements();assert.equal(m.snapshot(5000).duration_seconds,0);assert.equal(m.snapshot(5000).received_fps,null);
 m.start(1000);m.add({tracking:true,latency_ms:20},1100,1200);m.add({tracking:false,latency_ms:40},1300,1500);
 const result=m.snapshot(2000);assert.equal(result.frames,2);assert.equal(result.duration_seconds,1);
 assert.equal(result.mean_round_trip_ms,150);assert.equal(result.p95_round_trip_ms,200);assert.equal(result.mean_server_ms,30);
 assert.equal(result.tracking_percent,50);assert.equal(result.received_fps,1000/300);
 m.add({},2000,1999);assert.equal(m.snapshot(2000).frames,2);
});
test('latency percentile window stays bounded while mean includes the whole test',()=>{
 const m=new CameraMeasurements();m.start(0);m.add({},0,10000);
 for(let i=0;i<600;i++)m.add({tracking:true},20000+i*100,20010+i*100);
 const result=m.snapshot(90000);assert.equal(result.frames,601);assert.equal(result.p95_window_frames,600);
 assert.equal(result.p95_round_trip_ms,10);assert.equal(result.mean_round_trip_ms,16000/601);
});
test('manual comparison requires explicit finite observations and allows decimal plank durations',()=>{
 for(const input of ['', ' ', '-1', 'NaN', 'Infinity', '2.5'])assert.equal(compareObservation('squat',input,20,0),null);
 assert.deepEqual(compareObservation('squat','20',19,0),{manual:20,detected:19,signed_error:-1,absolute_error:1,unit:'reps'});
 assert.equal(compareObservation('plank','30.5',0,29).absolute_error,1.5);
 assert.equal(compareObservation('squat','0',1,0).absolute_error,1);
});
test('replay preserves nonuniform timestamps instead of assuming uniform FPS',()=>{const timeline=replayTimeline(4,[100,100.1,101.6,102],2);assert.deepEqual(timeline.map(t=>Number(t.toFixed(2))),[0,.1,1.6,2]);assert.equal(replayFrameAt(timeline,1),1);assert.equal(replayFrameAt(timeline,1.8),2);assert.equal(replayFrameAt(timeline,99),3)});
test('replay handles invalid timestamp metadata and missing frames',()=>{assert.deepEqual(replayTimeline(0,[],0),[]);assert.deepEqual(replayTimeline(3,[2,1,3],2),[0,1,2]);assert.deepEqual(replayTimeline(1,undefined,3),[0]);assert.equal(replayFrameAt([],3),0)});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function until(predicate){for(let i=0;i<100;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,10))}assert.fail('Expected asynchronous lifecycle operation did not finish')}
function harness(options={}){
 const originals=new Map(),requests=[],sockets=[],intervals=new Map(),draws=[];let nextTimer=0,cameraRequests=0,stops=0,finishRequests=0,refreshes=0;
 const override=(name,value)=>{originals.set(name,Object.getOwnPropertyDescriptor(globalThis,name));Object.defineProperty(globalThis,name,{configurable:true,writable:true,value})};
 const video={srcObject:null,readyState:2,videoWidth:640,videoHeight:480,play:async()=>{}};
 class FakeSocket{
  static OPEN=1;readyState=0;sent=[];
  constructor(){sockets.push(this);queueMicrotask(()=>{this.readyState=1;this.onopen?.()})}
  emit(value){this.onmessage?.({data:JSON.stringify(value)})}
  send(value){this.sent.push(value);if(typeof value==='string'){const command=JSON.parse(value);if((command.type==='start'||command.type==='demo')&&options.autoStart!==false)queueMicrotask(()=>this.emit({type:'started'}));if(command.type==='stop'&&options.autoStop!==false)queueMicrotask(()=>this.emit({type:'stopped'}))}}
  close(){this.readyState=3;queueMicrotask(()=>this.onclose?.())}
 }
 override('window',{});override('location',{protocol:'http:',host:'localhost:5173'});override('WebSocket',FakeSocket);
 override('navigator',{mediaDevices:{getUserMedia:async()=>{cameraRequests++;return {getTracks:()=>[{stop:()=>{stops++}}]}}}});
 override('document',{createElement:()=>({width:0,height:0,getContext:()=>({drawImage:(...args)=>draws.push(args)}),toBlob:callback=>callback(new Blob(['frame']))})});
 override('setInterval',callback=>{const id=++nextTimer;intervals.set(id,callback);return id});override('clearInterval',id=>intervals.delete(id));
 override('fetch',async(url,init={})=>{requests.push({url,init});let body={};let status=200;if(url==='/api/health')body={ultralytics_installed:options.poseInstalled!==false,model_weights_present:true,pose_model_loaded:false,training_active:options.trainingActive===true};else if(url==='/api/sessions')body={id:'session-01'};else if(url.endsWith('/finish')){finishRequests++;if(finishRequests<=(options.finishConflicts??0)){status=409;body={detail:'Stop live set first'}}}return new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}})});
 const {useCoach}=source('useCoach');let coach;
 function Probe(){coach=useCoach('squat',()=>{refreshes++},'person-test','Bodyweight squat');return null}
 renderToString(React.createElement(Probe));coach.video.current=video;
 return {coach,requests,sockets,intervals,draws,get cameraRequests(){return cameraRequests},get stops(){return stops},get finishRequests(){return finishRequests},get refreshes(){return refreshes},restore(){for(const [key,descriptor] of originals){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key]}}};
}
test('camera permission is never requested when pose dependencies are missing',async()=>{const h=harness({poseInstalled:false});try{await h.coach.start();assert.equal(h.cameraRequests,0);assert.equal(h.sockets.length,0);assert.equal(h.requests.filter(r=>r.url==='/api/sessions').length,0)}finally{h.restore()}});
test('live frames wait for started acknowledgement and preserve 4:3 camera aspect',async()=>{const h=harness({autoStart:false});try{const starting=h.coach.start();await until(()=>h.sockets[0]?.sent.length);assert.equal(h.intervals.size,0);h.sockets[0].emit({type:'started'});await starting;assert.equal(h.intervals.size,1);[...h.intervals.values()][0]();assert.deepEqual(h.draws[0].slice(1),[0,0,640,480]);const commands=h.sockets[0].sent.filter(v=>typeof v==='string').map(JSON.parse);assert.equal(commands[0].type,'start');const session=JSON.parse(h.requests.find(r=>r.url==='/api/sessions').init.body);assert.equal(session.variation,'Bodyweight squat');await h.coach.stop();assert.equal(h.coach.sessionId.current,null)}finally{h.restore()}});
test('stop releases camera immediately, waits for ACK, then retries finishing conflicts',async()=>{const h=harness({autoStop:false,finishConflicts:1});try{await h.coach.start();const stopping=h.coach.stop();assert.equal(h.stops,1);assert.equal(h.finishRequests,0);h.sockets[0].emit({type:'stopped'});await stopping;assert.equal(h.finishRequests,2);assert.equal(h.refreshes,1);assert.equal(h.coach.sessionId.current,null)}finally{h.restore()}});
test('unexpected disconnect closes camera and finalizes the session',async()=>{const h=harness();try{await h.coach.start();h.sockets[0].close();await until(()=>h.coach.sessionId.current===null);assert.equal(h.stops,1);assert.equal(h.finishRequests,1);assert.equal(h.intervals.size,0)}finally{h.restore()}});
test('fatal inference error stops capture and finalizes saved reps',async()=>{const h=harness();try{await h.coach.start();h.sockets[0].emit({type:'error',message:'Model failed'});await until(()=>h.coach.sessionId.current===null);assert.equal(h.stops,1);assert.equal(h.finishRequests,1);assert.equal(h.intervals.size,0)}finally{h.restore()}});
test('synthetic preview uses backend rep engine and never requests camera or creates session',async()=>{const h=harness();try{await h.coach.start(true);assert.equal(h.cameraRequests,0);assert.equal(h.requests.length,0);assert.equal(JSON.parse(h.sockets[0].sent[0]).type,'demo');[...h.intervals.values()][0]();assert.equal(JSON.parse(h.sockets[0].sent[1]).type,'tick');await h.coach.stop();assert.equal(h.finishRequests,0)}finally{h.restore()}});
test('late old socket events cannot reject or stop a newer session',async()=>{const h=harness();try{await h.coach.start();const old=h.sockets[0];await h.coach.stop();await h.coach.start();const current=h.sockets[1];old.emit({type:'error',message:'stale old socket'});old.onclose?.();await flush();assert.equal(h.coach.sessionId.current,'session-01');assert.equal(h.stops,1);assert.equal(current.readyState,1);await h.coach.stop()}finally{h.restore()}});

const {lightingLevel,cameraChecks}=source('setupChecks');
test('camera setup requires light, in-frame joints, tracking, and adequate body size',()=>{
 const points=Array.from({length:17},(_,i)=>[.3+(i%2)*.15,.1+i*.045,.9]);
 const frame={tracking:true,keypoints:points};assert.equal(cameraChecks(frame,100,'squat').ready,true);
 assert.equal(cameraChecks(frame,10,'squat').ready,false);assert.equal(cameraChecks(frame,null,'squat').ready,false);
 assert.equal(cameraChecks({...frame,tracking:false},100,'squat').ready,false);
 const cropped=points.map(p=>[...p]);cropped[15][1]=.99;cropped[16][2]=.1;
 assert.equal(cameraChecks({tracking:true,keypoints:cropped},100,'squat').fullBody,false);
 assert.equal(cameraChecks({tracking:true,keypoints:points.map(p=>[.5,.5,.9])},100,'squat').distance,false);
 assert.equal(lightingLevel(new Uint8ClampedArray([100,100,100,255])),100);
 assert.equal(lightingLevel(new Uint8ClampedArray()),null);
});
test('setup streams real frames without creating a saved session, then allows recording',async()=>{
 const h=harness();try{
  // Setup has the same start acknowledgement as recording.
  const starting=h.coach.start(false,true,{exercise:'plank',variation:''});await until(()=>h.sockets.length>0);
  h.sockets[0].emit({type:'started'});assert.equal(await starting,true);
  assert.equal(JSON.parse(h.sockets[0].sent[0]).type,'setup');assert.equal(JSON.parse(h.sockets[0].sent[0]).exercise,'plank');
  [...h.intervals.values()][0]();assert.equal(h.draws.length,1);
  assert.equal(h.requests.filter(r=>r.url==='/api/sessions').length,0);await h.coach.stop();assert.equal(h.finishRequests,0);
  assert.equal(await h.coach.start(),true);assert.equal(h.requests.filter(r=>r.url==='/api/sessions').length,1);await h.coach.stop();
 }finally{h.restore()}
});
const {expandPlan,validPlan,reachedTarget,remainingRest}=source('workouts');
test('workouts preserve order, expand sets, and distinguish valid hold time from reps',()=>{
 const steps=expandPlan([{exercise:'squat',sets:2,target:10,rest:60},{exercise:'plank',sets:1,target:30,rest:0}]);
 assert.deepEqual(steps.map(s=>[s.exercise,s.set]),[['squat',1],['squat',2],['plank',1]]);
 assert.equal(reachedTarget(steps[0],9,50),false);assert.equal(reachedTarget(steps[0],10,0),true);
 assert.equal(reachedTarget(steps[2],100,29.9),false);assert.equal(reachedTarget(steps[2],0,30),true);
 assert.equal(remainingRest(10000,1001),9);assert.equal(remainingRest(10000,11000),0);
 for(const value of [null,[],[{exercise:'squat',sets:0,target:10,rest:60}],[{exercise:'plank',sets:1,target:Infinity,rest:0}]])assert.equal(validPlan(value),false);
});

// Execute the workout hook's effects and async boundaries without a webcam or DOM.
function workoutHarness(options={}){
 const slots=[];let cursor=0,scheduled=false,disposed=false,current;const effects=[],calls=[];
 const schedule=()=>{if(!scheduled&&!disposed){scheduled=true;queueMicrotask(()=>{scheduled=false;if(!disposed)render()})}};
 const hooks={
  useState(initial){const i=cursor++;slots[i]??={value:typeof initial==='function'?initial():initial};return [slots[i].value,value=>{slots[i].value=typeof value==='function'?value(slots[i].value):value;schedule()}]},
  useRef(initial){const i=cursor++;slots[i]??={current:initial};return slots[i]},
  useEffect(effect,deps){const i=cursor++,old=slots[i];if(!old||deps.some((d,n)=>!Object.is(d,old.deps[n]))){slots[i]={deps,cleanup:old?.cleanup};effects.push(()=>{slots[i].cleanup?.();slots[i].cleanup=effect()})}}
 };
 const props={frame:{reps:0,hold_seconds:0},mode:'idle',busy:false,error:'',sessionId:null,
  prepare:async exercise=>{calls.push(['prepare',exercise]);props.mode='setup';props.frame={reps:0,hold_seconds:0};schedule();return true},
  begin:async()=>{props.mode='live';props.sessionId='recorded-set';return true},
  stop:async()=>{calls.push(['stop']);props.mode='idle';if(options.failStop)throw new Error('Persistence failed')}
 };
 const {useWorkout}=source('useWorkout',{__react:hooks});
 function render(){cursor=0;current=useWorkout(props);while(effects.length)effects.shift()()}
 render();return {get current(){return current},calls,update(value){Object.assign(props,value);render()},dispose(){disposed=true;for(const slot of slots)slot?.cleanup?.()}};
}
test('workout ends targets once, advances through zero rest, and completes final hold',async()=>{
 const h=workoutHarness();try{
  h.current.start([{exercise:'squat',sets:1,target:2,rest:0},{exercise:'plank',sets:1,target:3,rest:0}]);await flush();
  assert.equal(h.current.run.phase,'setup');await h.current.beginSet();await flush();
  h.update({frame:{reps:2,hold_seconds:0}});await flush();await flush();
  assert.deepEqual(h.calls.filter(c=>c[0]==='prepare'),[['prepare','squat'],['prepare','plank']]);
  assert.equal(h.current.run.results.length,1);assert.equal(h.current.run.results[0].session_id,'recorded-set');
  await h.current.beginSet();await flush();h.update({frame:{reps:100,hold_seconds:2}});await flush();assert.equal(h.current.run.phase,'active');
  h.update({frame:{reps:100,hold_seconds:3}});await flush();assert.equal(h.current.run.phase,'complete');
  assert.equal(h.current.run.results.length,2);assert.equal(h.calls.filter(c=>c[0]==='stop').length,2);
 }finally{h.dispose()}
});
test('pausing during rest resumes the next set without repeating a completed one',async()=>{
 const h=workoutHarness();try{
  h.current.start([{exercise:'squat',sets:2,target:1,rest:60}]);await flush();await h.current.beginSet();await flush();
  h.update({frame:{reps:1,hold_seconds:0}});await flush();assert.equal(h.current.run.phase,'rest');
  await h.current.pause();await flush();assert.equal(h.current.run.index,1);h.current.resume();await flush();
  assert.equal(h.current.step.set,2);assert.equal(h.current.run.results.length,1);assert.equal(h.current.run.phase,'setup');
 }finally{h.dispose()}
});
test('failed set finalization pauses a workout and does not credit the target',async()=>{
 const h=workoutHarness({failStop:true});try{
  h.current.start([{exercise:'squat',sets:1,target:1,rest:0}]);await flush();await h.current.beginSet();await flush();
  h.update({frame:{reps:1,hold_seconds:0}});await flush();assert.equal(h.current.run.phase,'paused');assert.equal(h.current.run.results.length,0);
 }finally{h.dispose()}
});

const {reviewMarkers,explainFlag}=source('review');
test('rep review groups contiguous flags and locates the nearest saved range marker',()=>{
 const lean={flag:'torso_lean',cue:'Keep your chest lifted',severity:2},depth={flag:'depth',cue:'Use more range',severity:2};
 const record={flags:[lean,depth],keypoints:[[],[],[],[],[]],timestamps:[10,10.1,10.4,10.8,11],depth_marker_time:10.42,min_angle:115,
  assessment_config:{metric:'knee_angle',depth_target:100,rules:[{flag:'torso_lean',feature:'torso_lean',operator:'max',threshold:55}]},
  frame_annotations:[[],[lean],[lean],[],[lean]].map(flags=>({flags,features:{torso_lean:65},state:'descending'}))};
 const markers=reviewMarkers(record);assert.equal(markers.length,3);
 assert.deepEqual(markers.map(m=>[m.index,m.end,m.summary]),[[1,2,false],[2,2,true],[4,4,false]]);
 assert.match(explainFlag(record,lean,1),/65.0/);assert.match(explainFlag(record,lean,1),/at most 55/);
 assert.match(explainFlag(record,depth),/115.0/);assert.match(explainFlag(record,depth),/whole rep/);
});
test('legacy or mismatched frame annotations never invent review events',()=>{
 assert.deepEqual(reviewMarkers({flags:[{flag:'depth'}],keypoints:[[]]}),[]);
 assert.deepEqual(reviewMarkers({flags:[],keypoints:[[],[]],frame_annotations:[{flags:[]}]}),[]);
 assert.match(explainFlag({flags:[]},{flag:'depth'}),/not saved/);
});

const {activeRun,percent,scoreDifference}=source('labTypes');
test('model lab distinguishes active jobs, missing scores and F1 percentage-point changes',()=>{
 for(const status of ['queued','running','cancelling'])assert.equal(activeRun({status}),true);
 for(const status of ['succeeded','failed','cancelled','interrupted'])assert.equal(activeRun({status}),false);
 assert.equal(percent(0),'0.0%');assert.equal(percent(.875),'87.5%');assert.equal(percent(undefined),'—');assert.equal(percent(NaN),'—');
 assert.equal(scoreDifference(.8,.7),'+10.0 points');assert.equal(scoreDifference(.5,.7),'-20.0 points');assert.equal(scoreDifference(.8,undefined),null);
});

test('an active training job blocks camera startup before requesting permission',async()=>{const h=harness({trainingActive:true});try{assert.equal(await h.coach.start(),false);assert.equal(h.cameraRequests,0);assert.equal(h.sockets.length,0)}finally{h.restore()}});
