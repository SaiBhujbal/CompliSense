import json
ev=[]
for line in open(r'D:\Study\CompliSense\_audit_b.jsonl',encoding='utf-8'):
    line=line.strip()
    if not line: continue
    d=json.loads(line); ev.append(d)
    snip=str(d.get('snippet') or d.get('response') or '')[:120]
    print(f"{d.get('node') or ('DONE' if d.get('done') else '?')}\tskipped={d.get('skipped')}\tflags={d.get('route_flags')}\tlens={d.get('analysis_lens')}\t{snip}")
print('TOTAL',len(ev))
done=[e for e in ev if e.get('done')]
print('HAS_DONE',bool(done),'ANSWER_LEN',len((done[0].get('response') if done else '') or ''))
if done:
    ans=done[0].get('response') or ''
    print('ANSWER_HEAD:', ans[:700].replace('\n',' | '))
    low=ans.lower()
    print('refusal_markers', [m for m in ['unavailable','will not guess','vector store','chroma','knowledge base','ingest'] if m in low])
