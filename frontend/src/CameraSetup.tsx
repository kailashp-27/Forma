import {useEffect,useState} from 'react';
import {cameraChecks} from './setupChecks';
import type {ExerciseId,Frame} from './types';
export default function CameraSetup({frame,brightness,exercise,busy,onBegin}:{frame:Frame;brightness:number|null;exercise:ExerciseId;busy:boolean;onBegin:()=>void}){
 const [sideConfirmed,setSideConfirmed]=useState(false),[steady,setSteady]=useState(0);
 const checks=cameraChecks(frame,brightness,exercise);
 useEffect(()=>{if(!checks.ready){setSteady(0);return}const timer=setInterval(()=>setSteady(n=>Math.min(n+1,3)),1000);return()=>clearInterval(timer)},[checks.ready]);
 // A frozen response cannot keep a previous green setup check valid.
 const [stale,setStale]=useState(false);
 useEffect(()=>{setStale(false);const timer=setTimeout(()=>{setStale(true);setSteady(0)},3000);return()=>clearTimeout(timer)},[frame]);
 return <section className="panel setup-assistant" aria-labelledby="setup-title"><h2 id="setup-title">Camera setup</h2><p className="small muted">Hold still for 3 seconds. No reps saved yet.</p>
 <ul className="setup-checks">{[{ok:checks.lighting,label:brightness===null?'Checking lighting…':brightness<45?'Add light in front of you':brightness>225?'Reduce bright light facing the camera':'Lighting ready'}, {ok:checks.fullBody,label:checks.fullBody?'Body visible':'Keep your full body in frame'}, {ok:checks.distance,label:checks.distance?'Distance ready':'Move closer while keeping your full body visible'}].map(item=><li key={item.label} className={item.ok&&!stale?'passed':''}>{item.ok&&!stale?'✓':'○'} {item.label}</li>)}</ul>
 <label className="side-confirmation"><input type="checkbox" checked={sideConfirmed} onChange={e=>setSideConfirmed(e.target.checked)}/>I am side-on to a fixed camera.</label>
 <p className="small muted">{stale?' Waiting for fresh tracking…':checks.ready?` Steady: ${steady}/3 seconds.`:''}</p>
 <button className="button primary" disabled={busy||!checks.ready||!sideConfirmed||steady<3||stale} onClick={onBegin}>Begin set</button></section>;
}
