import type {FormFlag,SavedRep} from './types';
export type ReviewMarker={index:number;end:number;flag:FormFlag;summary:boolean};
export function reviewMarkers(record:SavedRep):ReviewMarker[]{
 const count=record.keypoints?.length??0,annotations=record.frame_annotations;
 if(!count||!annotations||annotations.length!==count)return [];
 const markers:ReviewMarker[]=[],open=new Map<string,ReviewMarker>();
 annotations.forEach((frame,index)=>{
  const active=new Set(frame.flags.map(flag=>flag.flag));
  for(const key of open.keys())if(!active.has(key))open.delete(key);
  for(const flag of frame.flags){const previous=open.get(flag.flag);if(previous)previous.end=index;else{const marker={index,end:index,flag,summary:false};markers.push(marker);open.set(flag.flag,marker)}}
 });
 const depth=record.flags.find(flag=>flag.flag==='depth');
 if(depth&&record.depth_marker_time!=null&&record.timestamps?.length===count){
  let nearest=0;for(let i=1;i<count;i++)if(Math.abs(record.timestamps[i]-record.depth_marker_time)<Math.abs(record.timestamps[nearest]-record.depth_marker_time))nearest=i;
  markers.push({index:nearest,end:nearest,flag:depth,summary:true});
 }
 return markers.sort((a,b)=>a.index-b.index||b.flag.severity-a.flag.severity);
}
export function explainFlag(record:SavedRep,flag:FormFlag,index?:number){
 if(flag.flag==='depth'){
  const angle=record.min_angle,target=record.assessment_config?.depth_target;
  return typeof angle==='number'&&typeof target==='number'?`Deepest ${record.assessment_config?.metric.replaceAll('_',' ')}: ${angle.toFixed(1)}°. This rep's range target was ${target}° or less. This check summarizes the whole rep.`:'The completed rep did not reach its configured range target. Exact frame evidence was not saved.';
 }
 const rule=record.assessment_config?.rules?.find(r=>r.flag===flag.flag),value=index===undefined?null:record.frame_annotations?.[index]?.features[rule?.feature??''];
 if(rule&&typeof value==='number')return `${rule.feature.replaceAll('_',' ')}: ${value.toFixed(1)}°. The recorded rule expected ${rule.operator==='max'?'at most':'at least'} ${rule.threshold}°.`;
 return ({torso_lean:'The side-view torso angle exceeded the configured limit.',body_alignment:'The shoulder–hip–ankle angle fell below the configured alignment limit.',torso_swing:'The torso angle exceeded the configured swing proxy limit.'} as Record<string,string>)[flag.flag]??'A configured rule flagged this visible movement.';
}
