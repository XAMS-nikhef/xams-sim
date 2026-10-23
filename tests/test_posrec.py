"""Position-reconstruction toy: building a (u, v) -> (x, y) map and amstrax's bilinear lookup."""
import numpy as np

from xamssim import posrec


def test_build_and_lookup_roundtrip():
    rng = np.random.default_rng(1)
    x, y = rng.uniform(-20, 20, (2, 200000))
    u, v = np.tanh(x / 30), np.tanh(y / 30)                       # a smooth, invertible light response
    grid = posrec.build_map(u, v, x, y, smooth_bins=0.5)
    assert grid["n"] == 401 and len(grid["x"]) == 401 and grid["uv_min"] == -1.0
    xr, yr = posrec.lookup(u[:5000], v[:5000], grid)
    assert np.sqrt(np.mean((xr - x[:5000]) ** 2)) < 0.3 and np.sqrt(np.mean((yr - y[:5000]) ** 2)) < 0.3


def test_lookup_matches_amstrax_convention():
    # x grows with u (first index), y with v (second index), (u, v) clipped to the grid
    n = 401
    g = dict(uv_min=-1.0, step=0.005, n=n,
             x=np.repeat(np.linspace(-30, 30, n)[:, None], n, axis=1), y=np.repeat(np.linspace(-30, 30, n)[None, :], n, axis=0))
    x, y = posrec.lookup(np.array([0.5, 2.0]), np.array([-0.5, 0.0]), g)
    assert np.allclose(x, [15, 30], atol=0.2) and np.allclose(y, [-15, 0], atol=0.2)


def test_edge_extrapolation():
    """Beyond the simulated range the map continues outwards and stops at r_max (no pile-up at the border)."""
    rng = np.random.default_rng(2)
    r = 20 * np.sqrt(rng.random(300000)); phi = 2 * np.pi * rng.random(300000)
    x, y = r * np.cos(phi), r * np.sin(phi)
    u, v = x / 40, y / 40                                          # simulated range: |(u, v)| < 0.5
    g = posrec.build_map(u, v, x, y, smooth_bins=0.5, r_max=31.0)
    for rho in (0.55, 0.65):                                     # beyond the range: further out, along the ray
        xr, yr = posrec.lookup(np.array([rho, 0.0]), np.array([0.0, -rho]), g)
        assert np.all(np.hypot(xr, yr) > 20.5) and np.all(np.hypot(xr, yr) <= 31.0 + 1e-6)
    xr, yr = posrec.lookup(np.array([0.95]), np.array([0.0]), g)
    assert abs(np.hypot(xr, yr)[0] - 31.0) < 0.5 and abs(yr[0]) < 1.0      # capped at the wall, same direction
