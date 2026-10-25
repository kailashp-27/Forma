import type {ExerciseId} from './types';
export type PlanRow={exercise:ExerciseId;sets:number;target:number;rest:number};
export type WorkoutStep=PlanRow&{set:number};
export const defaultPlan:PlanRow[]=[{exercise:'squat',sets:2,target:10,rest:60},{exercise:'pushup',sets:2,target:10,rest:60},{exercise:'plank',sets:1,target:30,rest:60}];
export function validPlan(value:unknown):value is PlanRow[]{
 return Array.isArray(value)&&value.length>0&&value.length<=12&&value.every(row=>row&&['squat','pushup','plank','pullup'].includes(row.exercise)&&Number.isInteger(row.sets)&&row.sets>=1&&row.sets<=10&&Number.isInteger(row.target)&&row.target>=1&&row.target<=(row.exercise==='plank'?600:100)&&Number.isInteger(row.rest)&&row.rest>=0&&row.rest<=600);
}
export function expandPlan(plan:PlanRow[]):WorkoutStep[]{
 if(!validPlan(plan))throw new Error('Choose 1–12 exercises, 1–10 sets, 1–100 reps (or 600 hold seconds), and 0–600 rest seconds.');
 return plan.flatMap(row=>Array.from({length:row.sets},(_,i)=>({...row,set:i+1})));
}
export function reachedTarget(step:WorkoutStep,reps:number,hold:number){return (step.exercise==='plank'?hold:reps)>=step.target}
export function remainingRest(deadline:number,now:number){return Math.max(0,Math.ceil((deadline-now)/1000))}
