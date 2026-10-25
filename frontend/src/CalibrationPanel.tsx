import {useCallback,useEffect,useRef,useState} from 'react';
import {api,type CalibrationProfile,type CalibrationSettings,type ExerciseId,type SavedRep} from './types';

export default function CalibrationPanel({participant,exercise,variation,locked,onReview}:{participant:string;exercise:ExerciseId;variation:string;locked:boolean;onReview:()=>void}){
 const [candidates,setCandidates]=useState<SavedRep[]>([]),[profiles,setProfiles]=useState<CalibrationProfile[]>([]),[ids,setIds]=useState<string[]>([]),[proposal,setProposal]=useState<CalibrationSettings|null>(null),[loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const revision=useRef(0),query=new URLSearchParams({participant_id:participant,exercise,variation}).toString();
 const load=useCallback(async()=>{const token=++revision.current;setLoading(true);setError('');try{
  const result=await api<{profiles:CalibrationProfile[];candidates:SavedRep[]}>(`/calibrations?${query}`);
  if(token!==revision.current)return;setProfiles(result.profiles);setCandidates(result.candidates);setIds(selected=>selected.filter(id=>result.candidates.some(r=>r.id===id)));setProposal(null);
 }catch(e){if(token===revision.current)setError(String(e))}finally{if(token===revision.current)setLoading(false)}},[query]);
 useEffect(()=>{if(variation&&exercise!=='plank')void load();return()=>{revision.current++}},[load,variation,exercise]);
 const submit=async(save:boolean)=>{setBusy(true);setError('');setNotice('');try{
  const body=JSON.stringify({participant_id:participant,exercise,variation,record_ids:ids});
  if(save){await api('/calibrations',{method:'POST',body});await load();setNotice('Calibration saved. New sessions for this participant and variation will use it.')}else setProposal(await api<CalibrationSettings>('/calibrations/preview',{method:'POST',body}));
 }catch(e){setError(String(e));setProposal(null)}finally{setBusy(false)}};
 const disable=async(id:string)=>{setBusy(true);setError('');try{await api(`/calibrations/${id}/disable`,{method:'POST'});await load();setNotice('Default counting thresholds restored for new sessions.')}catch(e){setError(String(e))}finally{setBusy(false)}};
 const active=profiles.find(profile=>profile.enabled);
 return <section className="panel calibration-panel" aria-labelledby="calibration-title"><div className="section-title"><div><h2 id="calibration-title">Counting thresholds</h2><p>{participant} · {variation||exercise} · side view</p></div><button className="button secondary" disabled={busy||loading||!variation||exercise==='plank'} onClick={()=>void load()}>Refresh</button></div>
 {exercise==='plank'?<p className="notice">Plank uses alignment and valid hold time. Range calibration applies to squats, push-ups and pull-ups.</p>:<>
 <p className="small muted">Select 3–20 reviewed Good form reps to personalize counting.</p>
 <div className="calibration-current"><strong>{active?'Personal calibration active':'Default counting thresholds active'}</strong>{active?<><span>Extension {active.settings.extended}° · contraction {active.settings.contracted}° · {active.settings.examples.length} reviewed reps</span><button className="button secondary" disabled={locked||busy} onClick={()=>void disable(active.id)}>Restore defaults</button></>:null}</div>
 {loading?<p className="small" role="status">Loading reviewed repetitions…</p>:candidates.length?<fieldset className="calibration-candidates" disabled={locked||busy}><legend>{ids.length}/20 selected · {candidates.length} eligible reps</legend>{candidates.map(rep=><label key={rep.id}><input type="checkbox" checked={ids.includes(rep.id)} disabled={!ids.includes(rep.id)&&ids.length>=20} onChange={e=>{setIds(selected=>e.target.checked?[...selected,rep.id]:selected.filter(id=>id!==rep.id));setProposal(null)}}/><span>Rep {rep.rep_number} · {rep.duration.toFixed(1)}s · score {rep.quality}<small>{rep.created_at?new Date(rep.created_at).toLocaleString():rep.id}</small></span></label>)}</fieldset>:<div className="notice">Review at least 3 Good form reps at this variation to calibrate.</div>}
 <div className="button-row"><button className="button secondary" onClick={onReview}>Review in Dataset Studio</button><button className="button primary" disabled={locked||busy||loading||ids.length<3} onClick={()=>void submit(false)}>{busy?'Working…':'Preview calibration'}</button></div>
 {proposal?<div className="calibration-proposal"><h3>Proposed counting thresholds</h3><p>Extension: {proposal.defaults.extended}° → {proposal.extended}° · contraction: {proposal.defaults.contracted}° → {proposal.contracted}°</p><p className="small muted">{proposal.note} Estimates use robust per-rep angles from {proposal.examples.length} reviewed examples. Camera placement must stay consistent.</p><button className="button primary" disabled={locked||busy} onClick={()=>void submit(true)}>Save calibration</button></div>:null}
 </>}
 {error?<p className="error-banner" role="alert">{error}</p>:null}{notice?<p className="notice" role="status">{notice}</p>:null}
 <details className="inline-help"><summary>About calibration</summary><p>Changes counting only; form targets and quality scores stay the same. Profiles apply to new sessions for this participant and variation. Keep camera placement consistent.</p></details></section>;
}
