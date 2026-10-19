"""S6: light maps (lookup, edge bins) and the photon -> photoelectron step."""
import numpy as np

from xamssim import lightmap
from xamssim.plugins.light import _multinomial


def test_inside_fraction_and_fill():
    e = np.linspace(-3, 3, 7)
    f = lightmap._inside_fraction(e, e, 3.0)
    assert f[3, 3] == 1.0 and f[0, 0] < 0.1
    assert abs(f.sum() - np.pi * 9) < 0.5                     # area of the circle in bins of 1 mm²
    p = np.where(f >= 0.3, 1.0, 99.0)[None]                   # edge bins hold noise
    assert np.all(lightmap._fill_edge(p, f) == 1.0)


def test_lightmap_lookup(tmp_path):
    x = y = np.array([-1.0, 1.0])
    z = np.array([0.0, 2.0])
    p = np.zeros((lightmap.N_CHANNELS, 2, 2, 2), np.float32)
    p[0, :, :, 0], p[0, :, :, 1] = 0.1, 0.3                   # bottom: rises with z
    p[1, 1, :, :] = 0.2                                       # ch1: only at +x
    np.savez(tmp_path / "s1.npz", x=x, y=y, z=z, p=p)
    m = lightmap.LightMap(tmp_path / "s1.npz")
    q = m(np.array([0.0, 5.0]), np.array([0.0, 0.0]), np.array([1.0, -9.0]))
    assert q.shape == (2, lightmap.N_CHANNELS)
    assert np.isclose(q[0, 0], 0.2) and np.isclose(q[0, 1], 0.1)   # centre: linear between the voxel centres
    assert np.isclose(q[1, 0], 0.1) and np.isclose(q[1, 1], 0.2)   # outside the grid: its edge


def test_multinomial():
    rng = np.random.default_rng(1)
    n = np.array([0, 1000, 10 ** 6])
    p = np.tile([0.5, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0], (3, 1))
    k = _multinomial(rng, n, p)
    assert k.shape == (3, 7) and k[0].sum() == 0 and k[1].sum() <= 1000
    assert abs(k[2, 0] / 1e6 - 0.5) < 0.005 and abs(k[2, 1] / 1e6 - 0.1) < 0.005
    big = _multinomial(rng, np.array([100]), np.array([[0.8, 0.8, 0, 0, 0, 0, 0]]))   # sum > 1: scaled to all photons
    assert big.sum() == 100
