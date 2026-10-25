import {useEffect,useState} from 'react';
import {exercises,type ExerciseId} from './types';
import {defaultPlan,validPlan,type PlanRow} from './workouts';
import type {useWorkout} from './useWorkout';
const storageKey='forma.workout-plan.v1';
function readPlan(){try{const saved=JSON.parse(localStorage.getItem(storageKey)??'null');if(saved?.version===1&&validPlan(saved.rows))return saved.rows as PlanRow[]}catch{}return defaultPlan.map(row=>({...row}))}
export default function WorkoutPlans({workout,busy,mode}:{workout:ReturnType<typeof useWorkout>;busy:boolean;mode:string}){
 const [plan,setPlan]=useState<PlanRow[]>(readPlan),[storageError,setStorageError]=useState('');
 useEffect(()=>{try{localStorage.setItem(storageKey,JSON.stringify({version:1,rows:plan}));setStorageError('')}catch{setStorageError('Browser storage is unavailable. This plan will last until you close the page.')}},[plan]);
 const update=(index:number,patch:Partial<PlanRow>)=>setPlan(rows=>rows.map((row,i)=>i===index?{...row,...patch}:row));
 const locked=workout.locked||busy||mode!=='idle';
 const exportSummary=()=>{if(!workout.run)return;const url=URL.createObjectURL(new Blob([JSON.stringify({schema_version:1,...workout.run},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='forma-workout-summary.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 return <section className="panel workout-plans" aria-labelledby="workout-title"><div className="section-title"><div><h2 id="workout-title">Plan your sets</h2></div></div>
 <div className="workout-rows">{plan.map((row,i)=><div className="workout-row" key={i}>
  <label>Movement {i+1}<select disabled={locked} value={row.exercise} onChange={e=>update(i,{exercise:e.target.value as ExerciseId,target:e.target.value==='plank'?30:10})}>{exercises.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
  {([{key:'sets',label:'Sets',min:1,max:10},{key:'target',label:row.exercise==='plank'?'Hold seconds':'Reps / set',min:1,max:row.exercise==='plank'?600:100},{key:'rest',label:'Rest seconds',min:0,max:600}] as const).map(field=><label key={field.key}>{field.label}<input type="number" disabled={locked} min={field.min} max={field.max} step="1" value={row[field.key]} onChange={e=>update(i,{[field.key]:Math.max(field.min,Math.min(field.max,Math.round(Number(e.target.value)||field.min)))})}/></label>)}
  <button className="button secondary" aria-label={`Remove movement ${i+1}`} disabled={locked||plan.length===1} onClick={()=>setPlan(rows=>rows.filter((_,n)=>n!==i))}>Remove</button>
 </div>)}</div>
 <div className="button-row"><button className="button secondary" disabled={locked||plan.length>=12} onClick={()=>setPlan(rows=>[...rows,{exercise:'squat',sets:1,target:10,rest:60}])}>Add movement</button><button className="button primary" disabled={locked||!validPlan(plan)} onClick={()=>workout.start(plan)}>Start workout</button></div>
 {storageError?<p role="status" className="small">{storageError}</p>:null}
 {workout.run?<div className="workout-status" role="status"><h3>{workout.run.phase==='complete'?'Workout complete':workout.step?`${exercises.find(e=>e.id===workout.step!.exercise)?.name} · set ${workout.step.set}/${workout.step.sets}`:''}</h3>
 <p>{workout.run.results.length}/{workout.run.steps.length} sets completed · {workout.run.phase==='rest'?`Rest: ${workout.remaining}s`:workout.run.phase==='setup'?'Check camera setup, then begin your set':workout.run.phase==='active'?`Target: ${workout.step?.target} ${workout.step?.exercise==='plank'?'valid hold seconds':'reps'}`:workout.run.phase==='saving'?'Saving set…':workout.run.phase==='paused'?'Paused · resume restarts the current set':'All targets reached'}</p>
 <div className="button-row">{workout.run.phase==='paused'?<button className="button primary" disabled={busy} onClick={workout.resume}>Resume current set</button>:workout.run.phase!=='complete'?<button className="button secondary" disabled={busy||workout.run.phase==='saving'} onClick={()=>void workout.pause()}>Pause workout</button>:null}<button className="button secondary" disabled={busy||workout.run.phase==='saving'} onClick={()=>void workout.cancel()}>Close workout</button><button className="button secondary" disabled={!workout.run.results.length} onClick={exportSummary}>Export workout summary</button></div></div>:null}
 <details className="inline-help"><summary>How workouts work</summary><p>Plans save in this browser. Sets advance after rest. Pausing saves completed reps; resuming restarts the current set.</p></details>
 </section>;
}
