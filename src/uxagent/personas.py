from __future__ import annotations

import asyncio, hashlib, json, random
from datetime import datetime, timezone
from pathlib import Path
from .schemas import Persona
from .storage import write_json


def _quota(weights: dict[str,float], count: int):
    if not weights or any(v<0 for v in weights.values()) or abs(sum(weights.values())-1)>1e-6:
        raise ValueError("attribute proportions must be non-negative and sum to 1")
    exact={k:v*count for k,v in weights.items()}
    result={k:int(v) for k,v in exact.items()}
    left=count-sum(result.values())
    for key in sorted(weights,key=lambda k:(-(exact[k]-result[k]),k))[:left]:result[key]+=1
    return result


def generate_personas(config_path: str | Path, output_dir=".", provider_name="mock"):
    path=Path(config_path).resolve();cfg=json.loads(path.read_text(encoding="utf-8"))
    count=cfg.get("count")
    if not isinstance(count,int) or count<=0: raise ValueError("count must be a positive integer")
    seed=cfg.get("seed",0);mode=cfg.get("sampling_mode","quota")
    rng=random.Random(seed)
    example_path=path.parent/cfg.get("example_persona_file","persona.json")
    if example_path.suffix.lower()==".jsonl":
        examples=[Persona.model_validate_json(line) for line in example_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not examples:raise ValueError("example persona JSONL is empty")
        example=rng.choice(examples)
    else:
        example=Persona.model_validate_json(example_path.read_text(encoding="utf-8"))
    assignments=[{} for _ in range(count)]
    distributions={}
    for attr,weights in cfg.get("attributes",{}).items():
        if mode=="quota":
            quotas=_quota(weights,count);values=[value for value,n in quotas.items() for _ in range(n)];rng.shuffle(values)
        elif mode=="random":
            _quota(weights,1);keys=list(weights);probs=[weights[k] for k in keys];values=rng.choices(keys,probs,k=count)
            quotas={k:values.count(k) for k in keys}
        else:raise ValueError("sampling_mode must be quota or random")
        for row,value in zip(assignments,values):row[attr]=value
        distributions[attr]={"requested":weights,"assigned":quotas}
    generated=[];hashes=set();validation=[];usage={"requests":0,"input_tokens":0,"output_tokens":0,"tokens":0,"estimated":False}
    max_requests=int(cfg.get("max_llm_requests",count*3));max_tokens=int(cfg.get("max_total_tokens",50000))
    model="deterministic-template"
    if provider_name not in ("mock","live"):raise ValueError("provider_name must be mock or live")
    if provider_name=="live":
        from .llm import OpenAIProvider
        provider=OpenAIProvider();model=cfg.get("model","gpt-4o-mini")
    contexts=cfg.get("contexts",["통학 중 소지품을 빠르게 꺼낼 수 있는 구성을 중요하게 생각한다.","상품 설명에서 수납 공간과 크기 정보를 꼼꼼히 비교한다.","사용 후 관리가 쉬운 소재인지 함께 살펴본다.","검색 결과를 몇 가지 비교한 뒤 선택하는 편이다.","상품 상세의 구성품과 사용 상황을 확인한다.","조건에 맞는 후보를 찾은 뒤 상세 정보를 차분히 읽는다."])
    if not isinstance(contexts,list) or not contexts or any(not isinstance(item,str) or not item.strip() for item in contexts):
        raise ValueError("contexts must be a non-empty list of descriptions")
    rng.shuffle(contexts)
    for i,attrs in enumerate(assignments,1):
        values=example.model_dump()
        values["persona_id"]=f"p{i:03d}"
        if "digital_familiarity" in attrs:values["digital_familiarity"]=attrs["digital_familiarity"]
        values["constraints"]={**values["constraints"],**cfg.get("fixed_constraints",{})}
        prefs=list(values["preferences"])
        if attrs.get("digital_familiarity")=="낮음":prefs.append("안내 문구를 천천히 확인")
        elif attrs.get("digital_familiarity")=="높음":prefs.append("필터와 정렬 기능을 적극 활용")
        values["preferences"]=list(dict.fromkeys(prefs))
        values["background"]=values["background"].rstrip()+f" 디지털 숙련도는 {values['digital_familiarity']} 수준이다. {contexts[(i-1)%len(contexts)]}"
        values["preferences"].append(contexts[(i-1)%len(contexts)])
        candidate=None;digest=None;failure="generation_failed"
        for attempt in range(3):
            reserved_estimate=False
            try:
                if provider_name=="live":
                    prompt={"example_persona":example.model_dump(),"assigned_attributes":attrs,"fixed_constraints":cfg.get("fixed_constraints",{}),"instruction":"Return one fictional persona JSON with persona_id, background, digital_familiarity, preferences, constraints, intent. Preserve assigned attributes and fixed constraints. Do not add a prescribed success path or infer ability from age or gender."}
                    reservation=900+len(json.dumps(prompt,ensure_ascii=False))//4
                    if usage["requests"]>=max_requests or usage["tokens"]+reservation>max_tokens:
                        failure="generation_budget_exceeded";break
                    usage["requests"]+=1;usage["tokens"]+=reservation;reserved_estimate=True
                    response,reported=asyncio.run(provider.complete([{"role":"system","content":"Generate a varied but plausible fictional study persona. Output only JSON matching the requested fields."},{"role":"user","content":json.dumps(prompt,ensure_ascii=False)}],model,0.4,900))
                    if "input_tokens" in reported and "output_tokens" in reported:
                        input_tokens=reported["input_tokens"] or 0;output_tokens=reported["output_tokens"] or 0
                        usage["input_tokens"]+=input_tokens;usage["output_tokens"]+=output_tokens
                        usage["tokens"]+=input_tokens+output_tokens-reservation
                    else:usage["estimated"]=True
                    reserved_estimate=False
                    generated_values=json.loads(response)
                    generated_values["persona_id"]=f"p{i:03d}"
                    if generated_values.get("digital_familiarity")!=attrs.get("digital_familiarity",example.digital_familiarity):raise ValueError("assigned attribute changed")
                    if {**generated_values.get("constraints",{}),**cfg.get("fixed_constraints",{})}!=generated_values.get("constraints",{}):raise ValueError("fixed constraints changed")
                    values=generated_values
                candidate=Persona.model_validate(values)
                digest=hashlib.sha256(json.dumps(candidate.model_dump(exclude={"persona_id"}),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if digest in hashes:failure="duplicate_content";continue
                break
            except Exception as exc:
                if reserved_estimate:usage["estimated"]=True
                failure=str(exc)[:200]
        if candidate is None or digest is None or digest in hashes:
            validation.append({"persona_id":f"p{i:03d}","valid":False,"reason":failure});continue
        hashes.add(digest);generated.append(candidate)
        validation.append({"persona_id":candidate.persona_id,"valid":True,"assigned_attributes":attrs,"content_hash":digest})
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/"personas.jsonl").write_text("".join(p.model_dump_json()+"\n" for p in generated),encoding="utf-8")
    manifest={"seed":seed,"sampling_mode":mode,"requested_count":count,"generated_count":len(generated),"seeded_example_persona_id":example.persona_id,"example_source":str(example_path),"model":model,"prompt_version":"persona-1","usage":{"requests":usage["requests"],"input_tokens":usage["input_tokens"],"output_tokens":usage["output_tokens"],"tokens":usage["tokens"],"estimated":usage["estimated"],"max_requests":max_requests,"max_tokens":max_tokens},"distributions":distributions,"validation":validation,"failed_count":count-len(generated)}
    manifest_path=out/"generation_manifest.json"
    manifest.update({"generated_at":datetime.now(timezone.utc).isoformat(),"generation_id":cfg.get("generation_id"),
                     "start_url":cfg.get("start_url"),"task":cfg.get("task"),"background":example.background})
    write_json(manifest_path,manifest)
    return out/"personas.jsonl",len(generated),count
