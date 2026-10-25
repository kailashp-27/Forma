import type {ExerciseId,Frame} from './types';
export function lightingLevel(data:Uint8ClampedArray){
 if(!data.length)return null;
 let sum=0;for(let i=0;i<data.length;i+=4)sum+=.2126*data[i]+.7152*data[i+1]+.0722*data[i+2];
 return sum/(data.length/4);
}
export function cameraChecks(frame:Frame,brightness:number|null,exercise:ExerciseId){
 const points=frame.keypoints??[];
 const visible=(index:number)=>{const p=points[index];return p?.length>=3&&p.every(Number.isFinite)&&p[2]>=.4&&p[0]>.035&&p[0]<.965&&p[1]>.035&&p[1]<.965};
 const joints=exercise==='plank'?[5,11,15]:[5,7,9,11,13,15];
 const fullBody=frame.tracking===true&&[0,1].some(side=>joints.every(i=>visible(i+side)));
 const confident=points.filter(p=>p.length>=3&&p.every(Number.isFinite)&&p[2]>=.4);
 const span=confident.length?Math.max(...confident.map(p=>p[1]))-Math.min(...confident.map(p=>p[1])):0;
 const width=confident.length?Math.max(...confident.map(p=>p[0]))-Math.min(...confident.map(p=>p[0])):0;
 const distance=fullBody&&Math.max(span,width)>=.3;
 const lighting=brightness!==null&&brightness>=45&&brightness<=225;
 return {fullBody,distance,lighting,ready:fullBody&&distance&&lighting};
}
