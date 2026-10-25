export type ExerciseId = 'squat'|'pushup'|'plank'|'pullup';
export type FormFlag = {flag:string;cue:string;severity:number};
export type AssessmentConfig={metric:string;extended:number;contracted:number;depth_target?:number;rules?:{feature:string;operator:string;threshold:number;flag:string}[]};
export type FrameAnnotation={features:Record<string,number|null>;state:string;flags:FormFlag[]};
export type SavedRep={id:string;session_id:string;exercise:string;participant_id:string;label:string|null;rule_label:string;rep_number:number;quality:number;duration:number;flags:FormFlag[];keypoints?:number[][][];timestamps?:number[];frame_count?:number;aspect_ratio?:number;created_at:string;min_angle?:number;frame_annotations?:FrameAnnotation[];depth_marker_time?:number|null;assessment_config?:AssessmentConfig;calibration_id?:string|null};
export type CalibrationSettings={version:number;metric:string;extended:number;contracted:number;defaults:{extended:number;contracted:number};examples:{record_id:string;low_angle:number;high_angle:number;frames:number}[];note:string};
export type CalibrationProfile={id:string;participant_id:string;exercise:string;variation:string;enabled:boolean;created_at:string;settings:CalibrationSettings};
export type CompletedRep = {rep_number:number;duration:number;quality:number;flags:FormFlag[];[key:string]:unknown};
export type Frame = {type:string; keypoints?:number[][];width?:number;height?:number;fps?:number;latency_ms?:number;state?:string;reps?:number;hold_seconds?:number;quality?:number|null;cue?:string;flags?:FormFlag[];tracking?:boolean;rep_completed?:CompletedRep;error?:string;message?:string};
export type Health = {status:string;pose_model_loaded:boolean;ultralytics_installed:boolean;model_weights_present:boolean;training_active?:boolean};
export type ExerciseConfig = {id:ExerciseId;name:string;ladder:string[];target_reps:number;target_hold_seconds:number;limitations:string[]};
export type Progression = {exercise:ExerciseId;name:string;ladder:string[];current_variation:string;next_variation:string;qualifying_sets:number;required_sets:number;ready:boolean;rule:string;note:string};
export type Session = {id:number|string;exercise?:string;started_at?:string;created_at?:string;ended_at?:string;reps?:unknown[];rep_count?:number;total_reps?:number;quality?:number;avg_quality?:number;calibration?:CalibrationProfile|null;[key:string]:unknown};
export const exercises: {id:ExerciseId;name:string;description:string;tag:string;focus:string;position:string}[] = [
 {id:'squat',name:'Squat',description:'Build a stronger foundation.',tag:'LOWER BODY',focus:'Depth · torso control',position:'Stand side-on, 2–3 metres from the camera. Keep your full body in frame.'},
 {id:'pushup',name:'Push-up',description:'Strength from the ground up.',tag:'UPPER BODY',focus:'Depth · body alignment',position:'Place the camera side-on at hip height. Keep your shoulders and ankles visible.'},
 {id:'plank',name:'Plank',description:'Find strength in stillness.',tag:'CORE & STABILITY',focus:'Alignment · hold time',position:'Use a side view at floor height. Keep your shoulder, hip and ankle visible.'},
 {id:'pullup',name:'Pull-up',description:'Own the entire movement.',tag:'UPPER BODY',focus:'Extension · controlled tempo',position:'Use a side view with the bar and your entire body in frame. Chin clearance is not measured in this version.'},
];
export async function api<T>(path:string, init?:RequestInit):Promise<T>{const r=await fetch(`/api${path}`,{signal:AbortSignal.timeout(10000),...init,headers:{'Content-Type':'application/json',...init?.headers}});if(!r.ok){let detail='';try{detail=JSON.stringify((await r.json()).detail)}catch{}throw new Error(`${r.status}: ${detail||r.statusText}`)}return r.json()}
