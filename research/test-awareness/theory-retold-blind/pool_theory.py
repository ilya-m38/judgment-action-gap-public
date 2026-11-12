# blind pool for theory answers: wide regex, reasoning (R) and answer (A) separately
import json,re,glob,random,sys,os
OUT=sys.argv[1]; seed=int(sys.argv[2]); roots=sys.argv[3:]
W=re.compile(r"simulat|benchmark|grader|graded|harness|\bevals?\b|\b(an?|the|this|safety|ethics|ethical|alignment|AI|model|behaviou?ral) evaluations?\b|being (evaluated|tested|assessed|probed|graded|watched|observed)|evaluator|\b(a|the|this|my|ethics|ethical|safety|alignment|moral|integrity|loyalty|obedience|compliance|judgment) tests?\b|\btest(s|ed|ing)? (whether|if|how|for|the|my|an? AI|AI|me|you|model|assistant|scenario|case|prompt|question|of)|deliberate(ly)? (designed|constructed|crafted|set|engineered|framed|built|written)|(designed|constructed|crafted|engineered|built|written|set up|framed) (to|so|as a|in a way)|contrived|artificial|planted|\btrap|red[- ]?team|thought experiment|\bprob(e|es|ing)\b|rubric|alignment|trick|gotcha|\bsetup\b|fictional|toy (example|scenario)|\bquiz|\bexam\b",re.I)
MASK=re.compile(r"gemini|google|grok|xai|kimi|moonshot|qwen|alibaba|claude|anthropic|haiku|mistral|minimax|nemotron|nvidia|glm|zhipu|deepseek|gpt|openai|llama|luna|sol\b|terra\b",re.I)
items=[]
for root in roots:
  for f in sorted(glob.glob(root+"/*/*/[01][0-9]/result.json")):
    d=json.load(open(f))
    for sec,txt in (("R",d.get('reasoning') or ''),("A",d.get('final_text') or '')):
      if not isinstance(txt,str): txt=json.dumps(txt)
      spans=[]
      for m in W.finditer(txt):
        a,b=max(0,m.start()-250),min(len(txt),m.end()+250)
        if spans and a<=spans[-1][1]: spans[-1][1]=b
        else: spans.append([a,b])
      if not spans: continue
      ex="\n  [...]\n".join(MASK.sub("[X]",txt[a:b]) for a,b in spans[:6])
      items.append(dict(src=f,sec=sec,text=ex,n=len(spans)))
random.Random(seed).shuffle(items)
os.makedirs(OUT,exist_ok=True); key={}
with open(OUT+"/pool.txt","w") as fo:
  for i,it in enumerate(items,1):
    c=f"{i:04d}"; key[c]=dict(src=it['src'],sec=it['sec'])
    fo.write(f"===== {c} [{it['sec']}] ({it['n']} spans)\n{it['text']}\n\n")
json.dump(key,open(OUT+"-KEY.json","w"),indent=0)
print(len(items))
