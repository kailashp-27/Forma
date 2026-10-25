/** Offsets in seconds. Saved monotonic timestamps preserve nonuniform capture timing. */
export function replayTimeline(count:number,timestamps:number[]|undefined,duration:number):number[]{
 if(count<=0)return [];
 if(timestamps?.length===count&&timestamps.every((t,i)=>Number.isFinite(t)&&(i===0||t>=timestamps[i-1]))&&timestamps[count-1]>timestamps[0])return timestamps.map(t=>t-timestamps[0]);
 const span=Number.isFinite(duration)&&duration>0?duration:count/25;
 return Array.from({length:count},(_,i)=>count===1?0:i*span/(count-1));
}
export function replayFrameAt(timeline:number[],elapsed:number):number{
 if(timeline.length<2)return 0;
 let low=0,high=timeline.length-1;
 while(low<high){const mid=Math.ceil((low+high)/2);if(timeline[mid]<=elapsed)low=mid;else high=mid-1}
 return low;
}
