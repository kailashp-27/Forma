import {useEffect,useRef,useState} from 'react';
import type {ExerciseId,Frame} from './types';
import {expandPlan,reachedTarget,remainingRest,type PlanRow,type WorkoutStep} from './workouts';
type Phase='setup'|'active'|'saving'|'rest'|'paused'|'complete';
type Result={exercise:ExerciseId;set:number;target:number;reps:number;hold_seconds:number;session_id:number|string|null};
type Run={steps:WorkoutStep[];index:number;phase:Phase;deadline:number;results:Result[]};
export function useWorkout({frame,mode,busy,error,sessionId,prepare,begin,stop}:{frame:Frame;mode:string;busy:boolean;error:string;sessionId:number|string|null;prepare:(exercise:ExerciseId)=>Promise<boolean>;begin:()=>Promise<boolean>;stop:()=>Promise<void>}){
 const [run,setRun]=useState<Run|null>(null),[remaining,setRemaining]=useState(0);
 const latest=useRef({frame,sessionId,prepare,begin,stop});latest.current={frame,sessionId,prepare,begin,stop};
 const phase=run?.phase,index=run?.index,step=run?.steps[run.index];
 useEffect(()=>{if(phase!=='setup'||!step)return;let alive=true;
  void latest.current.prepare(step.exercise).then(ok=>{if(alive&&!ok)setRun(r=>r?{...r,phase:'paused'}:r)}).catch(()=>{if(alive)setRun(r=>r?{...r,phase:'paused'}:r)});
  return()=>{alive=false};
 },[phase,index,step]);
 useEffect(()=>{if(phase==='active'&&mode==='live'&&step&&reachedTarget(step,frame.reps??0,frame.hold_seconds??0))setRun(r=>r?.phase==='active'?{...r,phase:'saving'}:r)},[phase,mode,step,frame]);
 useEffect(()=>{if(phase!=='saving'||!step)return;let alive=true;const observed=latest.current;
  void observed.stop().then(()=>{if(!alive)return;setRun(r=>{
   if(!r)return r;const results=[...r.results,{exercise:step.exercise,set:step.set,target:step.target,reps:observed.frame.reps??0,hold_seconds:observed.frame.hold_seconds??0,session_id:observed.sessionId}];
   return {...r,results,phase:r.index+1===r.steps.length?'complete':'rest',deadline:Date.now()+step.rest*1000};
  })}).catch(()=>{if(alive)setRun(r=>r?{...r,phase:'paused'}:r)});
  return()=>{alive=false};
 },[phase,step]);
 useEffect(()=>{if(phase!=='rest'||!run)return;const deadline=run.deadline;
  const tick=()=>{const left=remainingRest(deadline,Date.now());setRemaining(left);if(left===0)setRun(r=>r?.phase==='rest'?{...r,index:r.index+1,phase:'setup'}:r)};
  tick();const timer=setInterval(tick,250);return()=>clearInterval(timer);
 },[phase,run?.deadline]);
 useEffect(()=>{if(!busy&&phase==='active'&&(error||mode==='idle'))setRun(r=>r?{...r,phase:'paused'}:r)},[busy,error,phase,mode]);
 const start=(plan:PlanRow[])=>{setRemaining(0);setRun({steps:expandPlan(plan),index:0,phase:'setup',deadline:0,results:[]})};
 const beginSet=async()=>{try{const ok=await latest.current.begin();if(run)setRun(r=>r?{...r,phase:ok?'active':'paused'}:r)}catch{setRun(r=>r?{...r,phase:'paused'}:r)}};
 const pause=async()=>{setRun(r=>r&&r.phase!=='complete'?{...r,index:r.phase==='rest'?r.index+1:r.index,phase:'paused'}:r);try{await latest.current.stop()}catch{/* Coach retains the persistence error for retry. */}};
 const cancel=async()=>{setRun(null);try{await latest.current.stop()}catch{/* Coach retains the persistence error for retry. */}};
 return {run,step,remaining,start,beginSet,pause,cancel,resume:()=>setRun(r=>r?{...r,phase:'setup'}:r),locked:!!run&&phase!=='complete'};
}
