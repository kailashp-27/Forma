import {useEffect,useMemo,useRef,useState} from 'react';
import {Pause,Play} from 'lucide-react';
import type {SavedRep} from './types';
import {replayTimeline,replayFrameAt} from './replay';
import {reviewMarkers,explainFlag} from './review';
const edges=[[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
export default function KeypointPlayer({record}:{record:SavedRep}){
 const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false),playhead=useRef(0);
 const markers=useMemo(()=>reviewMarkers(record),[record]);
 const count=record.keypoints?.length??0;playhead.current=index;
 const timeline=useMemo(()=>replayTimeline(count,record.timestamps,record.duration),[count,record.timestamps,record.duration]);
 useEffect(()=>{setIndex(0);setPlaying(false)},[record.id]);
 useEffect(()=>{if(!playing||count<2)return;const start=performance.now(),offset=timeline[playhead.current]??0,span=Math.max(timeline.at(-1)??0,record.duration,.04);let raf=0;const loop=(now:number)=>{const elapsed=(offset+(now-start)/1000)%(span+.08);setIndex(replayFrameAt(timeline,elapsed));raf=requestAnimationFrame(loop)};raf=requestAnimationFrame(loop);return()=>cancelAnimationFrame(raf)},[playing,count,timeline,record.duration]);
 const points=record.keypoints?.[Math.min(index,count-1)]??[],width=500,height=500/(record.aspect_ratio||1);
 const annotations=record.frame_annotations?.length===count?record.frame_annotations:undefined;
 const active=annotations?.[index],metric=record.assessment_config?.metric;
 const span=timeline.at(-1)||1;
 const chartPoints=annotations?.flatMap((a,i)=>{const v=a.features[metric??''];return typeof v==='number'?[`${20+(timeline[i]??0)/span*460},${110-v/180*90}`]:[]}).join(' ');
 const jump=(frame:number)=>{setPlaying(false);setIndex(frame)};
 return <div className="keypoint-player"><div className="keypoint-stage"><svg viewBox={`0 0 ${width} ${height}`} aria-label={`Recorded keypoints, frame ${index+1} of ${count}`} role="img">{edges.map(([a,b])=>{const p=points[a],q=points[b];return p&&q&&p[2]>=.4&&q[2]>=.4?<line key={`${a}-${b}`} x1={p[0]*width} y1={p[1]*height} x2={q[0]*width} y2={q[1]*height}/>:null})}{points.map((p,i)=>p[2]>=.4?<circle key={i} cx={p[0]*width} cy={p[1]*height} r="3"/>:null)}</svg>{!count?<p>No keypoint sequence saved for this rep.</p>:null}<span>KEYPOINT REPLAY · NO VIDEO</span></div><div className="playback-controls"><button className="icon-button" aria-label={playing?'Pause replay':'Play replay'} disabled={count<2} onClick={()=>setPlaying(!playing)}>{playing?<Pause size={17}/>:<Play size={17}/>}</button><input type="range" min="0" max={Math.max(0,count-1)} value={index} disabled={!count} aria-label="Recorded frame" onChange={e=>{setPlaying(false);setIndex(Number(e.target.value))}}/><small>{count?index+1:0}/{count}</small></div><section className="rep-evidence" aria-label="Form evidence">
 <h3>Rep {record.rep_number} · form review</h3>
 {record.calibration_id?<p className="small muted">Personal counting calibration was used for this rep.</p>:null}
 {annotations&&metric?<><p className="small muted">{(timeline[index]??0).toFixed(2)}s · {active?.state.replaceAll('_',' ')} · {metric.replaceAll('_',' ')} {typeof active?.features[metric]==='number'?`${active.features[metric]!.toFixed(1)}°`:'unavailable'}</p>
 <svg className="angle-trace" viewBox="0 0 500 130" role="img" aria-label="Recorded movement angle over time with flagged moments"><polyline points={chartPoints}/>{record.assessment_config?.depth_target!==undefined?<line className="target-line" x1="20" x2="480" y1={110-record.assessment_config.depth_target/180*90} y2={110-record.assessment_config.depth_target/180*90}/>:null}<line className="playhead-line" x1={20+(timeline[index]??0)/span*460} x2={20+(timeline[index]??0)/span*460} y1="10" y2="115"/>{markers.map((m,i)=><circle key={i} cx={20+(timeline[m.index]??0)/span*460} cy="118" r="3"/>)}<text x="20" y="12">180°</text><text x="470" y="108">0°</text></svg>
 <p className="small">{active?.flags.length?active.flags.map(flag=>`${flag.cue} ${explainFlag(record,flag,index)}`).join(' '):'No frame-level rule flag at this moment.'}</p>
 {markers.length?<div className="review-markers">{markers.map((marker,i)=><button key={i} className="button secondary" onClick={()=>jump(marker.index)}>{(timeline[marker.index]??0).toFixed(2)}s · {marker.flag.flag.replaceAll('_',' ')}{marker.summary?' · rep summary':''}</button>)}</div>:<p className="small muted">No rule events were recorded in this rep.</p>}
 </>:<p className="notice">This older record has no saved frame-level rule evidence. Its skeleton and rep summary remain available.</p>}
 {record.flags.length?<ul className="review-explanations">{record.flags.map(flag=><li key={flag.flag}><strong>{flag.cue}</strong><span>{explainFlag(record,flag)}</span></li>)}</ul>:<p className="small muted">No rep-level rule flags.</p>}
 <details className="inline-help"><summary>About this replay</summary><p>Markers show recorded rule evidence. Range markers summarize the whole rep and jump to the nearest saved deepest frame. Angles come from the smoothed tracking used during assessment; the skeleton shows saved camera keypoints.</p>
 <p>Joints below 0.4 confidence are hidden. Replay follows saved timestamps when available. It does not contain video.</p></details></section></div>
}
