import re,json,copy
from pathlib import Path
class Atom(str): pass
def parse(text):
 stack=[]; out=None
 for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
  if t=='(':
   a=[]
   if stack: stack[-1].append(a)
   stack.append(a)
  elif t==')': out=stack.pop()
  else:
   if t.startswith('"'): v=json.loads(t)
   else:
    try: v=float(t) if '.' in t else int(t)
    except ValueError: v=Atom(t)
   stack[-1].append(v)
 return out
def one(n,k,default=None): return next((x for x in n if isinstance(x,list) and x and x[0]==k),default)
def many(n,k): return [x for x in n if isinstance(x,list) and x and x[0]==k]
def prop(n,k): return next((x for x in many(n,'property') if x[1]==k),None)
def dumps(n,lev=0):
 if isinstance(n,list):
  if all(not isinstance(v,list) for v in n):return '('+' '.join(dumps(v) for v in n)+')'
  s='('; first=True
  for v in n:
   if isinstance(v,list):s+='\n'+'\t'*(lev+1)+dumps(v,lev+1)
   else:s+=('' if first else ' ')+dumps(v)
   first=False
  return s+'\n'+'\t'*lev+')'
 if isinstance(n,Atom):return str(n)
 if isinstance(n,str):return json.dumps(n,ensure_ascii=False)
 if isinstance(n,float):return format(n,'.7f').rstrip('0').rstrip('.') or '0'
 return str(n)
def read(path):return parse(Path(path).read_text())
def libsym(lib,name):
 root=read('/usr/share/kicad/symbols/'+lib+'.kicad_sym'); syms={s[1]:s for s in many(root,'symbol')}
 def resolve(name):
  n=copy.deepcopy(syms[name]); e=one(n,'extends')
  if e:
   base=resolve(e[1]); n.remove(e)
   keys={x[0] for x in n if isinstance(x,list) and x[0] not in ['property','symbol']}
   props={p[1] for p in many(n,'property')}
   for x in base[2:]:
    if x[0]=='property' and x[1] in props:continue
    if x[0] in keys:continue
    n.append(x)
  for s in many(n,'symbol'):s[1]=re.sub(r'^.*(_\d+_\d+)$',name+r'\1',s[1])
  return n
 return resolve(name)
if __name__=='__main__':
 root=read('bldc_health.kicad_sch'); libs={s[1]:s for s in many(one(root,'lib_symbols'),'symbol')}
 for inst in many(root,'symbol'):
  ref=prop(inst,'Reference')[2]
  if ref.startswith(('U','J','F')):
   print(ref,one(inst,'at'))
   for unit in many(libs[one(inst,'lib_id')[1]],'symbol'):
    for pin in many(unit,'pin'):print(' ',one(pin,'number')[1],one(pin,'name')[1],one(pin,'at'))
