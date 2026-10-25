"""Readiness evidence from the same reviewed records used by local training."""
from collections import Counter
from ml.audit import audit_records
from .config import CONFIGS


def prepare_dataset(records, exercise):
    config=CONFIGS[exercise]
    expected=['good','depth']+[r['flag'] for r in config.get('rules',[])] if exercise!='plank' else ['good','body_alignment']
    expected=list(dict.fromkeys(expected))
    excluded=Counter()
    eligible=[]
    for record in records:
        if not record.get('session_finished_at'): reason='unfinished_session'
        elif not record.get('label'): reason='unlabeled'
        elif record['label'] in ('unusable','unobservable'): reason=record['label']
        elif record['label'] not in expected: reason='unsupported_label'
        elif record.get('view')!='side': reason='unsupported_view'
        else:
            eligible.append(record)
            continue
        excluded[reason]+=1
    audit=audit_records(eligible,exercise)
    split=audit['split']
    held_out_only=[]
    if split:
        train=set(split['train_people']);test=set(split['test_people'])
        held_out_only=sorted({r['label'] for r in eligible if r['participant_id'] in test}-{r['label'] for r in eligible if r['participant_id'] in train})
    blockers=[]
    if exercise=='plank': blockers.append('Plank holds have no saved repetition sequences. Collect supported rep exercises first.')
    if len(audit['participant_counts'])<3: blockers.append('Collect reviewed examples from at least three participants.')
    if len(audit['class_counts'])<2: blockers.append('Review at least two supported form classes.')
    if audit['errors']: blockers.append('Review invalid sequences and mark unsuitable records unusable before training.')
    if split and not audit['training_ready']: blockers.append('Training participants must include at least two classes.')
    if held_out_only: blockers.append('Held-out-only classes need training-person examples: '+', '.join(held_out_only))
    coverage=[]
    for label in expected:
        count=audit['class_counts'].get(label,0)
        people=sum(counts.get(label,0)>0 for counts in audit['participant_counts'].values())
        coverage.append({'label':label,'samples':count,'participants':people,'target_samples':150,'target_participants':3,
                         'missing_samples':max(0,150-count),'missing_participants':max(0,3-people)})
    report={'exercise':exercise,'total_records':len(records),'reviewed_records':len(eligible),'excluded':dict(excluded),
            'coverage':coverage,'audit':audit,'blockers':blockers,'training_ready':bool(audit['training_ready'] and not blockers),
            'note':'Readiness checks minimum structure and split coverage. Collection goals and classifier accuracy require further real-participant evidence.'}
    return eligible,report
