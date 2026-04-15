import json, os, sys

tasks = {
    'Prevention': r'C:\Users\tommi\AppData\Local\Temp\claude\c--AI-Workspaces-Claude-Code-Workspace---Tom-projects-Console-dashboards-eu-lice-treatment-analysis\dfe7bae3-078a-458d-9697-cb652b3572d7\tasks\a6d9014e90bc75d3f.output',
    'Treatment':  r'C:\Users\tommi\AppData\Local\Temp\claude\c--AI-Workspaces-Claude-Code-Workspace---Tom-projects-Console-dashboards-eu-lice-treatment-analysis\dfe7bae3-078a-458d-9697-cb652b3572d7\tasks\a0b3da0ca13c37bce.output',
}
out_dir = r'c:/AI Workspaces/Claude Code Workspace - Tom/projects/Console/dashboards/eu-lice-treatment-analysis/reviews/FR'

for seg, path in tasks.items():
    raw = open(path, encoding='utf-8', errors='replace').read()
    candidates = []
    i = 0
    L = len(raw)
    while i < L:
        if raw[i] == '{':
            depth = 0
            j = i
            in_str = False
            esc = False
            while j < L:
                c = raw[j]
                if esc:
                    esc = False
                elif c == chr(92):  # backslash
                    esc = True
                elif c == '"':
                    in_str = not in_str
                elif not in_str:
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            chunk = raw[i:j+1]
                            if '"totalReviews"' in chunk[:500] and '"reviews"' in chunk:
                                candidates.append(chunk)
                            break
                j += 1
            i = j + 1 if depth == 0 else i + 1
        else:
            i += 1
    best = None
    for c in sorted(candidates, key=len, reverse=True):
        try:
            parsed = json.loads(c)
            if 'totalReviews' in parsed and 'reviews' in parsed:
                best = parsed
                break
        except Exception as e:
            continue
    if not best:
        print(f'{seg}: NO valid JSON found ({len(candidates)} candidates)')
        continue
    out = os.path.join(out_dir, seg, 'voc.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(best, f, ensure_ascii=False, indent=1)
    print(f'{seg}: total={best["totalReviews"]} avg={best["avgRating"]} starDist={best["starDist"]} reviews_len={len(best["reviews"])} -> {out}')
