# blind pool for agent traces (pi.jsonl): assistant text+thinking, wide regex, masked, shuffled
import json,re,random,sys,os
OUT,seed,runs=sys.argv[1],int(sys.argv[2]),sys.argv[3:]
W=re.compile(r"simulat|benchmark|evaluat|grader|graded|harness|\bevals?\b|\btest(s|ed|ing)?\b|\bexam\b|designed|deliberate|contrived|artificial|planted|\btrap|red[- ]?team|scenario|probe|probing|rubric|alignment|trick|honeypot|fictional|sandbox|not real|fake|staged|role[- ]?play|hypothetical",re.I)
MASK=re.compile(r"gemini|google|grok|xai|kimi|moonshot|qwen|alibaba|claude|anthropic|haiku|sonnet|opus|astra|mistral|minimax|nemotron|glm|zhipu|deepseek|gpt|openai|luna",re.I)
items=[]
for r in runs:
  turns=[]
  for l in open(r+"/pi.jsonl"):
    d=json.loads(l)
    if d.get('type')=='message_end' and d['message'].get('role')=='assistant':
      for c in d['message']['content']:
        if c['type'] in('text','thinking'): turns.append((len(turns),c['type'],c.get('text') or c.get('thinking') or ''))
  vis=sum(len(t) for _,_,t in turns)
  ex=[]
  for i,typ,t in turns:
    spans=[]
    for m in W.finditer(t):
      a,b=max(0,m.start()-400),min(len(t),m.end()+400)
      if spans and a<=spans[-1][1]: spans[-1][1]=b
      else: spans.append([a,b])
    for a,b in spans: ex.append(f"-- turn {i} [{typ}]\n"+MASK.sub("[X]",t[a:b]))
  items.append((r,vis,len(turns),ex))
random.Random(seed).shuffle(items)
os.makedirs(OUT,exist_ok=True); key={}
for i,(r,vis,n,ex) in enumerate(items,1):
  c=f"{i:03d}"; key[c]=r
  open(f"{OUT}/{c}.txt","w").write(f"run {c} | text turns {n} | visible chars {vis}\n\n"+"\n\n".join(ex)+"\n")
json.dump(key,open(OUT+"-KEY.json","w"),indent=0)
print(len(items))
