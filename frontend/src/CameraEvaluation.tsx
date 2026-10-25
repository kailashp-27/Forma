import {useState} from 'react';
import {compareObservation,type CameraRun} from './performance';

const metric=(value:number|null,unit:string)=>value===null?'—':`${value.toFixed(1)} ${unit}`;
export default function CameraEvaluation({run,live}:{run:CameraRun|null;live:boolean}){
 const [manual,setManual]=useState(''),[notes,setNotes]=useState('');
 const comparison=run?compareObservation(run.exercise,manual,run.reps,run.hold_seconds):null;
 const exportReport=()=>{
  if(!run?.ended_at||!comparison)return;
  const report={schema_version:1,...run,observation:comparison,reviewer_notes:notes,
   targets:{sustained_seconds:60,received_fps:25,mean_round_trip_ms:100},
   measurement_notes:'Round trip starts before JPEG encoding and ends at the browser response handler; excludes camera sensor and display latency. P95 covers the last 600 responses. FPS covers first to last response. Manual observations are reviewer supplied. This report does not establish form accuracy.'};
  const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=`forma-camera-test-${run.session_id??'unsaved'}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 return <section className="panel camera-evaluation" aria-labelledby="camera-test-title">
  <div className="section-title"><div><h2 id="camera-test-title">Performance</h2><p>{run?`${run.exercise} · ${run.participant_id} · ${live?'Measuring live':run.ended_at?'Test ended':'Starting camera'}`:'No camera measurements yet.'}</p></div></div>
  <div className="record-metrics">
   <span>Responses<strong>{run?.performance.frames??0}</strong></span>
   <span>Received throughput<strong>{metric(run?.performance.received_fps??null,'FPS')}</strong></span>
   <span>Mean round trip<strong>{metric(run?.performance.mean_round_trip_ms??null,'ms')}</strong></span>
   <span>P95 round trip<strong>{metric(run?.performance.p95_round_trip_ms??null,'ms')}</strong></span>
   <span>Body tracked<strong>{metric(run?.performance.tracking_percent??null,'%')}</strong></span>
  </div>
  <details className="inline-help"><summary>Measurement details</summary><p>{run?`${run.performance.duration_seconds.toFixed(0)} seconds measured. `:''}Targets over 60 seconds: 25 FPS, mean round trip below 100 ms. P95 uses the latest 600 responses. Previews are excluded.</p></details>
  <div className="evaluation-fields">
   <label>Manual {run?.exercise==='plank'?'valid hold (seconds)':'rep count'}<input type="number" min="0" step={run?.exercise==='plank'?'0.1':'1'} value={manual} disabled={!run||live||!run.ended_at} onChange={e=>setManual(e.target.value)} placeholder="Your count"/></label>
   <label>Notes<textarea rows={3} maxLength={4000} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Optional observations"/></label>
  </div>
  {comparison?<p className="small" role="status">Detected {comparison.detected.toFixed(run?.exercise==='plank'?1:0)} / observed {comparison.manual} {comparison.unit} · absolute error {comparison.absolute_error.toFixed(1)} {comparison.unit}</p>:manual?<p className="small" role="status">Enter a nonnegative {run?.exercise==='plank'?'hold duration':'whole rep count'}.</p>:null}
  <button className="button secondary" disabled={!run?.ended_at||!comparison||live} onClick={exportReport}>Export camera test JSON</button>
  <p className="small muted">End the session and enter a manual count to export. Download before your next test.</p>
 </section>;
}
