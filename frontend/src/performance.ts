import type {Frame} from './types';

export class CameraMeasurements {
 private startedAt:number|null=null;
 private count=0;
 private tracked=0;
 private firstResponse:number|null=null;
 private lastResponse=0;
 private totalLatency=0;
 private latencies:number[]=[];
 private serverTotal=0;
 private serverCount=0;
 start(now:number){this.startedAt=now}
 add(frame:Frame,capturedAt:number,receivedAt:number){
  if(!Number.isFinite(capturedAt)||!Number.isFinite(receivedAt)||receivedAt<capturedAt)return;
  this.count++;if(frame.tracking===true)this.tracked++;
  this.firstResponse??=receivedAt;this.lastResponse=receivedAt;
  const latency=receivedAt-capturedAt;this.totalLatency+=latency;
  this.latencies.push(latency);if(this.latencies.length>600)this.latencies.shift();
  if(Number.isFinite(frame.latency_ms)&&frame.latency_ms!>=0){this.serverTotal+=frame.latency_ms!;this.serverCount++}
 }
 snapshot(now:number){
  const sorted=[...this.latencies].sort((a,b)=>a-b);
  return {frames:this.count,duration_seconds:this.startedAt===null?0:Math.max(0,now-this.startedAt)/1000,
   received_fps:this.count>1&&this.firstResponse!==null&&this.lastResponse>this.firstResponse?(this.count-1)*1000/(this.lastResponse-this.firstResponse):null,
   mean_round_trip_ms:this.count?this.totalLatency/this.count:null,
   p95_round_trip_ms:sorted.length?sorted[Math.ceil(sorted.length*.95)-1]:null,
   p95_window_frames:sorted.length,mean_server_ms:this.serverCount?this.serverTotal/this.serverCount:null,
   tracking_percent:this.count?this.tracked/this.count*100:null};
 }
}
export type CameraPerformance=ReturnType<CameraMeasurements['snapshot']>;
export type CameraRun={session_id:number|string|null;exercise:string;participant_id:string;variation:string;started_at:string;ended_at?:string;reps:number;hold_seconds:number;performance:CameraPerformance};

export function compareObservation(exercise:string,manual:string,reps:number,hold:number){
 if(!manual.trim())return null;
 const observed=Number(manual);
 if(!Number.isFinite(observed)||observed<0||(exercise!=='plank'&&!Number.isInteger(observed)))return null;
 const measured=exercise==='plank'?hold:reps;
 return {manual:observed,detected:measured,signed_error:measured-observed,absolute_error:Math.abs(measured-observed),unit:exercise==='plank'?'seconds':'reps'};
}
