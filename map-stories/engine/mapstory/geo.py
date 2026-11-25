"""Sphere math, routes and the perspective globe camera.

Coordinates: unit sphere, x toward (0N, 0E), y toward (0N, 90E), z toward the north pole.
Camera distance `d` is the height above the surface in Earth radii (3.5 = whole globe, 0.05 = a city).
"""
import math
import numpy as np


def ll2v(lat, lon):
    a, o = math.radians(lat), math.radians(lon)
    return np.array([math.cos(a) * math.cos(o), math.cos(a) * math.sin(o), math.sin(a)])


def ll2v_arr(lonlat):
    """(n,2) [lon, lat] degrees -> (n,3)"""
    a = np.radians(np.asarray(lonlat, np.float64))
    lon, lat = a[:, 0], a[:, 1]
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], 1)


def v2ll(v):
    v = v / np.linalg.norm(v)
    return math.degrees(math.asin(max(-1, min(1, v[2])))), math.degrees(math.atan2(v[1], v[0]))


def angle(p, q):
    return math.acos(max(-1.0, min(1.0, float(np.dot(p, q)))))


def slerp(p, q, e):
    d = angle(p, q)
    if d < 1e-6:
        return p
    return (math.sin((1 - e) * d) * p + math.sin(e * d) * q) / math.sin(d)


# easing
def ease(x):
    x = max(0., min(1., x)); return x * x * x * (x * (x * 6 - 15) + 10)


def eout(x):
    x = max(0., min(1., x)); return 1 - (1 - x) ** 3


def eback(x):
    x = max(0., min(1., x)); c = 1.7; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def route_points(waypoints, n=400, lift=0.0, smooth=3, offset_km=0.0):
    """great-circle chain through [(lat, lon), ...], Chaikin-smoothed on the sphere -> (m,3).
    lift > 0 raises the middle of the line off the surface (flight arcs).
    offset_km shifts the line sideways (positive = to the right of travel), e.g. a retreat drawn beside an advance."""
    vs = [ll2v(*p) for p in waypoints]
    lens = [max(1e-6, angle(vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    tot = sum(lens); out = []
    for i in range(len(vs) - 1):
        m = max(2, int(n * lens[i] / tot))
        for j in range(m):
            out.append(slerp(vs[i], vs[i + 1], j / m))
    out.append(vs[-1]); out = np.array(out)
    for _ in range(smooth):
        q = [out[0]]
        for i in range(len(out) - 1):
            q += [0.75 * out[i] + 0.25 * out[i + 1], 0.25 * out[i] + 0.75 * out[i + 1]]
        q.append(out[-1]); out = np.array(q); out /= np.linalg.norm(out, axis=1)[:, None]
    if offset_km:
        tang = np.gradient(out, axis=0)
        side = np.cross(tang, out); side /= np.maximum(np.linalg.norm(side, axis=1), 1e-12)[:, None]
        out = out + side * (offset_km / 6371.0)
        out /= np.linalg.norm(out, axis=1)[:, None]
    s = np.linspace(0, 1, len(out))
    return out * (1 + lift * np.sin(np.pi * s))[:, None]


def cum_length(pts):
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    c = np.concatenate([[0], np.cumsum(seg)])
    return c / max(c[-1], 1e-9)


class Cam:
    """perspective camera looking at surface point (lat, lon) from height d, tilted toward the north by `tilt` degrees.
    oy shifts the look-at point on screen (pixels, negative = higher), e.g. to keep the subject above vertical captions."""

    def __init__(self, lat, lon, d, tilt, W, H, fov=40.0, oy=0.0):
        self.W, self.H, self.oy = W, H, oy
        self.TH = math.tan(math.radians(fov) / 2); self.ASP = W / H
        P = ll2v(lat, lon); o = math.radians(lon)
        U = P; E = np.array([-math.sin(o), math.cos(o), 0.0]); N = np.cross(U, E)
        t = math.radians(tilt)
        self.C = P + d * (math.cos(t) * U - math.sin(t) * N)
        F = P - self.C; F /= np.linalg.norm(F)
        up0 = math.cos(t) * N + math.sin(t) * U
        R = np.cross(F, up0); R /= np.linalg.norm(R); Up = np.cross(R, F)
        self.F, self.R, self.U, self.d = F, R, Up, d
        self.lat, self.lon, self.tilt = lat, lon, tilt

    def project(self, q):
        """(n,3) points -> (n,2) pixels, visible mask (in front of the camera and not hidden by the globe)"""
        q = np.asarray(q, np.float64).reshape(-1, 3)
        v = q - self.C; z = v @ self.F
        zs = np.where(np.abs(z) < 1e-9, 1e-9, z)
        x = (v @ self.R) / (zs * self.TH * self.ASP); y = (v @ self.U) / (zs * self.TH)
        px = np.stack([(x + 1) / 2 * self.W, (1 - y) / 2 * self.H + self.oy], 1)
        L = np.linalg.norm(v, axis=1); dirn = v / np.maximum(L, 1e-12)[:, None]
        b = dirn @ self.C; c = self.C @ self.C - 1; disc = b * b - c
        s = -b - np.sqrt(np.maximum(disc, 0))
        vis = (z > 0) & ~((disc > 0) & (s < L - 1e-4) & (s > 0))
        return px, vis

    def pt(self, lat, lon):
        px, vis = self.project(ll2v(lat, lon)[None])
        return (float(px[0, 0]), float(px[0, 1])) if vis[0] else None

    def px_size(self):
        """ground size of one pixel at the look-at point, radians"""
        return self.d * 2 * self.TH / self.H


def fit_distance(r, W, H, fov=40.0):
    """height that keeps a cap of angular radius r (radians) inside the narrower half-FOV"""
    th = math.tan(math.radians(fov) / 2)
    h = math.atan(th * min(1.0, W / H))
    r = min(r, math.radians(80))
    return max(0.02, math.cos(r) + math.sin(r) / math.tan(h) - 1)


ZOOMS = {'globe': 72.0, 'continent': 26.0, 'country': 9.0, 'region': 3.6, 'city': 1.1, 'street': 0.35}


def zoom_distance(z, W, H):
    """'country' / degrees (number) -> camera height"""
    deg = ZOOMS[z] if isinstance(z, str) else float(z)
    return fit_distance(math.radians(deg), W, H)


def frame_points(latlons, W, H, pad=1.3):
    """center + height that frame every (lat, lon)"""
    vs = np.array([ll2v(*p) for p in latlons])
    c = vs.mean(0)
    if np.linalg.norm(c) < 1e-6:
        c = vs[0]
    c /= np.linalg.norm(c)
    r = max(angle(c, v) for v in vs) * pad + math.radians(0.6)
    lat, lon = v2ll(c)
    return lat, lon, fit_distance(r, W, H)
