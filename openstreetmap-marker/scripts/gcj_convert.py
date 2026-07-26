#!/usr/bin/env python3
"""GCJ-02 (Mars/China coordinate system, returned by Amap/Tencent/Apple Maps in mainland China)
-> WGS-84 (OSM/Leaflet basemap coordinate system) conversion.

Usage:
  python3 gcj_convert.py <lng> <lat>              # single point, outputs "wgs_lat,wgs_lng"
  python3 gcj_convert.py --json in.json out.json  # batch convert lat/lng fields of every object in a JSON array
"""
import sys, json, math


def gcj02_to_wgs84(lng, lat):
    a = 6378245.0
    ee = 0.00669342162296594323

    def out_of_china(lng, lat):
        return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)

    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret

    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    if out_of_china(lng, lat):
        return lng, lat

    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] != "--json":
        lng, lat = float(sys.argv[1]), float(sys.argv[2])
        wlng, wlat = gcj02_to_wgs84(lng, lat)
        print(f"{wlat:.6f},{wlng:.6f}")
    elif len(sys.argv) == 4 and sys.argv[1] == "--json":
        with open(sys.argv[2], encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            wlng, wlat = gcj02_to_wgs84(item["lng"], item["lat"])
            item["lat"], item["lng"] = round(wlat, 6), round(wlng, 6)
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Converted {len(data)} points -> {sys.argv[3]}")
    else:
        print(__doc__)
        sys.exit(1)
