"""Independent geometric acceptance (requires Shapely, uses only synthetic data)."""
import json, subprocess, math
from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
cases=json.loads(subprocess.check_output(['node',str(Path(__file__).with_name('test_planar_polygon.js')),'--json']))
def sub(a,b): return [x-y for x,y in zip(a,b)]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
for case in cases:
    p=case['polygon']; o=p[0]; u=sub(p[1],o); length=math.sqrt(dot(u,u)); u=[v/length for v in u]
    n=[0,0,0]
    for a,b in zip(p,p[1:]+p[:1]): n=[x+y for x,y in zip(n,cross(sub(a,o),sub(b,o)))]
    length=math.sqrt(dot(n,n)); n=[v/length for v in n]; v=cross(n,u)
    def project(a): return [dot(sub(a,o),u),dot(sub(a,o),v)]
    polygon=Polygon([project(a) for a in p]); assert polygon.is_valid
    triangles=[Polygon([project(a) for a in t]) for t in case['triangles']]
    union=unary_union(triangles); total=sum(t.area for t in triangles)
    assert abs(polygon.area-case['area'])<1e-9
    assert abs(total-polygon.area)<1e-9
    assert union.difference(polygon).area<1e-9
    assert polygon.difference(union).area<1e-9
    assert abs(total-union.area)<1e-9
    for t in case['triangles']: assert dot(cross(sub(t[1],t[0]),sub(t[2],t[0])),n)>0
print(f'planar-polygon Shapely: {len(cases)} variants; area/coverage/outside/overlap/winding PASS')
