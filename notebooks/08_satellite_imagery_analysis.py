#!/usr/bin/env python3
"""
Experiment 08: Satellite Imagery Analysis for Military Base Monitoring

Goal: Determine what military activity indicators we can reliably extract from
Sentinel-2 10m imagery using unsupervised CV algorithms. No training data needed.

Datasets:
  - Chkalovsk (Kaliningrad airbase) — runways, aircraft aprons, fuel storage
  - Kronstadt (naval base) — port facilities, ship berths, dry docks
  - Pskov 76th VDV (airborne division) — barracks, motor pool, helipad

Methods tested:
  1. Spectral indices — bare soil, impervious surface, vegetation stress
  2. Texture analysis (GLCM) — active vs inactive zones
  3. Edge density — infrastructure density estimation
  4. SSIM temporal change detection (simulated with spatial variance)
  5. Band ratio anomaly detection — fuel/construction signatures
  6. Super-resolution assessment — what's gained from 10m→2m upsampling

Reference: Sentinel-2 bands used:
  B2 (490nm Blue, 10m), B3 (560nm Green, 10m), B4 (665nm Red, 10m),
  B8 (842nm NIR, 10m), B11 (1610nm SWIR1, 20m), B12 (2190nm SWIR2, 20m)
"""

import json
import os
import sys

import cv2
import numpy as np
import tifffile
from scipy import ndimage
from skimage.feature import graycomatrix, graycoprops
from skimage.metrics import structural_similarity as ssim
from skimage.morphology import disk
from skimage.filters import rank

DATA_DIR = "/tmp/research"
SITES = ["chkalovsk", "kronstadt", "pskov"]
SITE_TYPES = {
    "chkalovsk": "airbase",
    "kronstadt": "naval",
    "pskov": "airborne",
}

results = {}


def load_multispectral(site):
    """Load 6-band GeoTIFF: B2, B3, B4, B8, B11, B12."""
    path = os.path.join(DATA_DIR, f"{site}_6band.tif")
    data = tifffile.imread(path).astype(np.float32)
    # Shape: (bands, height, width) or (height, width, bands)
    if data.ndim == 3 and data.shape[0] <= 6:
        pass  # Already (bands, H, W)
    elif data.ndim == 3 and data.shape[2] <= 6:
        data = data.transpose(2, 0, 1)
    bands = {"B2": data[0], "B3": data[1], "B4": data[2],
             "B8": data[3], "B11": data[4], "B12": data[5]}
    return bands


def load_rgb(site):
    """Load 2048px PNG thumbnail."""
    path = os.path.join(DATA_DIR, f"{site}_2048.png")
    img = cv2.imread(path)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT 1: Spectral Indices
# Which indices best separate military infrastructure from background?
# ═══════════════════════════════════════════════════════════════════

def compute_indices(bands):
    """Compute military-relevant spectral indices."""
    eps = 1e-10
    B2, B3, B4, B8, B11, B12 = (bands[k] for k in ["B2", "B3", "B4", "B8", "B11", "B12"])

    indices = {}

    # NDVI — vegetation health (negative = bare soil / impervious)
    indices["NDVI"] = (B8 - B4) / (B8 + B4 + eps)

    # NDBI — Normalized Difference Built-up Index (urban/impervious)
    indices["NDBI"] = (B11 - B8) / (B11 + B8 + eps)

    # BSI — Bare Soil Index (construction, cleared ground, vehicle tracks)
    indices["BSI"] = ((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2) + eps)

    # Concrete/Asphalt ratio (SWIR2/SWIR1 > 1.0 = impervious)
    indices["SWIR_ratio"] = B12 / (B11 + eps)

    # Modified NDWI — water bodies / fuel storage
    indices["MNDWI"] = (B3 - B11) / (B3 + B11 + eps)

    # Enhanced vegetation index — sensitive to canopy density
    indices["EVI"] = 2.5 * (B8 - B4) / (B8 + 6*B4 - 7.5*B2 + 1 + eps)

    # Iron oxide index — disturbed soil, construction sites
    indices["FeOx"] = B4 / (B3 + eps)

    return indices


print("=" * 70)
print("EXPERIMENT 1: Spectral Indices")
print("=" * 70)

for site in SITES:
    bands = load_multispectral(site)
    indices = compute_indices(bands)

    site_results = {}
    for name, arr in indices.items():
        valid = arr[np.isfinite(arr)]
        site_results[name] = {
            "mean": round(float(np.mean(valid)), 4),
            "std": round(float(np.std(valid)), 4),
            "p10": round(float(np.percentile(valid, 10)), 4),
            "p90": round(float(np.percentile(valid, 90)), 4),
        }

    results[f"exp1_{site}"] = site_results
    print(f"\n{site} ({SITE_TYPES[site]}):")
    for name, stats in site_results.items():
        print(f"  {name:12s}: mean={stats['mean']:+.3f}  std={stats['std']:.3f}  "
              f"[p10={stats['p10']:+.3f}, p90={stats['p90']:+.3f}]")

# Key question: can we segment "active military zones" using index thresholds?
print("\n→ Segmentation test: NDBI > 0 AND BSI > 0 = 'built/active' pixels")
for site in SITES:
    bands = load_multispectral(site)
    indices = compute_indices(bands)
    active = (indices["NDBI"] > 0) & (indices["BSI"] > 0)
    pct = 100 * np.sum(active) / active.size
    print(f"  {site}: {pct:.1f}% active pixels")


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT 2: Texture Analysis (GLCM)
# Can texture distinguish active facilities from empty ground?
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("EXPERIMENT 2: GLCM Texture Analysis")
print("=" * 70)

for site in SITES:
    bands = load_multispectral(site)
    # Use B8 (NIR, 10m) — most contrast between structures and vegetation
    gray = bands["B8"]
    # Clip outliers then normalize to 0-63 for GLCM (64 levels)
    p1, p99 = np.percentile(gray[gray > 0], [1, 99])
    gray = np.clip(gray, p1, p99)
    gray = ((gray - p1) / (p99 - p1 + 1e-10) * 63).astype(np.uint8)

    # Divide into 8x8 grid patches for spatial texture mapping
    h, w = gray.shape
    ph, pw = h // 8, w // 8
    texture_map = np.zeros((8, 8, 4))  # contrast, dissimilarity, homogeneity, energy

    for i in range(8):
        for j in range(8):
            patch = gray[i*ph:(i+1)*ph, j*pw:(j+1)*pw]
            glcm = graycomatrix(patch, distances=[1], angles=[0, np.pi/4],
                                levels=64, symmetric=True, normed=True)
            texture_map[i, j, 0] = graycoprops(glcm, "contrast").mean()
            texture_map[i, j, 1] = graycoprops(glcm, "dissimilarity").mean()
            texture_map[i, j, 2] = graycoprops(glcm, "homogeneity").mean()
            texture_map[i, j, 3] = graycoprops(glcm, "energy").mean()

    # High contrast + high dissimilarity = complex structure (active facility)
    # Low contrast + high energy = uniform (empty field, water)
    activity_score = texture_map[:, :, 0] * texture_map[:, :, 1]
    uniformity_score = texture_map[:, :, 3]

    active_patches = np.sum(activity_score > np.percentile(activity_score, 75))
    uniform_patches = np.sum(uniformity_score > np.percentile(uniformity_score, 75))

    results[f"exp2_{site}"] = {
        "mean_contrast": round(float(texture_map[:, :, 0].mean()), 2),
        "mean_dissimilarity": round(float(texture_map[:, :, 1].mean()), 2),
        "mean_homogeneity": round(float(texture_map[:, :, 2].mean()), 2),
        "active_patches_pct": round(active_patches / 64 * 100, 1),
    }

    print(f"\n{site} ({SITE_TYPES[site]}):")
    print(f"  Mean contrast: {texture_map[:,:,0].mean():.2f}")
    print(f"  Mean dissimilarity: {texture_map[:,:,1].mean():.2f}")
    print(f"  Mean homogeneity: {texture_map[:,:,2].mean():.2f}")
    print(f"  Activity score (contrast×dissim): "
          f"high-patches={active_patches}/64 ({active_patches/64*100:.0f}%)")


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT 3: Edge Density — infrastructure fingerprint
# More edges = more structures, roads, equipment
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("EXPERIMENT 3: Edge Density Analysis")
print("=" * 70)

for site in SITES:
    rgb = load_rgb(site)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Canny edges at multiple thresholds
    edges_loose = cv2.Canny(gray, 30, 80)
    edges_tight = cv2.Canny(gray, 50, 150)

    # Edge density per 256px patch (each patch ≈ 500m at 2048px/4km)
    ph, pw = 256, 256
    densities = []
    for y in range(0, gray.shape[0] - ph, ph):
        for x in range(0, gray.shape[1] - pw, pw):
            patch = edges_tight[y:y+ph, x:x+pw]
            densities.append(np.sum(patch > 0) / (ph * pw))

    densities = np.array(densities)
    high_density = np.sum(densities > 0.15)  # >15% edge pixels = complex infrastructure

    results[f"exp3_{site}"] = {
        "mean_edge_density": round(float(densities.mean()), 4),
        "max_edge_density": round(float(densities.max()), 4),
        "high_density_patches": int(high_density),
        "total_patches": len(densities),
    }

    print(f"\n{site} ({SITE_TYPES[site]}):")
    print(f"  Mean edge density: {densities.mean():.3f}")
    print(f"  Max edge density: {densities.max():.3f}")
    print(f"  High-density patches (>15%): {high_density}/{len(densities)}")
    print(f"  Edge density std: {densities.std():.3f}")


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT 4: Band Ratio Anomaly Detection
# Which pixels have spectral signatures of fuel, concrete, vehicles?
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("EXPERIMENT 4: Material-Specific Anomaly Detection")
print("=" * 70)

for site in SITES:
    bands = load_multispectral(site)
    eps = 1e-10

    # Concrete/asphalt: high SWIR2/SWIR1 ratio (>1.0)
    concrete = bands["B12"] / (bands["B11"] + eps)
    concrete_pct = 100 * np.sum(concrete > 1.05) / concrete.size

    # Fuel/oil: low NDVI + high SWIR absorption
    ndvi = (bands["B8"] - bands["B4"]) / (bands["B8"] + bands["B4"] + eps)
    fuel_sig = (ndvi < 0.1) & (bands["B12"] > np.percentile(bands["B12"], 80))
    fuel_pct = 100 * np.sum(fuel_sig) / fuel_sig.size

    # Vehicle metal: high B8 reflectance + low NDVI (shiny metal in NIR)
    metal_sig = (bands["B8"] > np.percentile(bands["B8"], 90)) & (ndvi < 0.2)
    metal_pct = 100 * np.sum(metal_sig) / metal_sig.size

    # Fresh construction: bare soil (BSI > 0.1) + not water (MNDWI < 0)
    bsi = ((bands["B11"] + bands["B4"]) - (bands["B8"] + bands["B2"])) / \
          ((bands["B11"] + bands["B4"]) + (bands["B8"] + bands["B2"]) + eps)
    mndwi = (bands["B3"] - bands["B11"]) / (bands["B3"] + bands["B11"] + eps)
    construction = (bsi > 0.1) & (mndwi < 0)
    construction_pct = 100 * np.sum(construction) / construction.size

    results[f"exp4_{site}"] = {
        "concrete_pct": round(concrete_pct, 2),
        "fuel_signature_pct": round(fuel_pct, 2),
        "metal_signature_pct": round(metal_pct, 2),
        "construction_pct": round(construction_pct, 2),
    }

    print(f"\n{site} ({SITE_TYPES[site]}):")
    print(f"  Concrete/asphalt: {concrete_pct:.1f}% of pixels")
    print(f"  Fuel/oil signature: {fuel_pct:.1f}%")
    print(f"  Metal reflectance: {metal_pct:.1f}%")
    print(f"  Construction/bare soil: {construction_pct:.1f}%")


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT 5: Spatial Autocorrelation — regular vs organic patterns
# Military installations have geometric regularity (grid layouts,
# parallel runways, rectangular buildings)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("EXPERIMENT 5: Spatial Regularity (FFT-based)")
print("=" * 70)

for site in SITES:
    rgb = load_rgb(site)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)

    # 2D FFT — military bases show peaks at regular spatial frequencies
    f_transform = np.fft.fft2(gray)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.log(np.abs(f_shift) + 1)

    # Radial power spectrum — peaks at specific frequencies = regular patterns
    cy, cx = magnitude.shape[0] // 2, magnitude.shape[1] // 2
    y, x = np.ogrid[:magnitude.shape[0], :magnitude.shape[1]]
    r = np.sqrt((x - cx)**2 + (y - cy)**2).astype(int)

    radial_profile = ndimage.mean(magnitude, r, range(0, min(cy, cx)))
    radial_profile = np.array(radial_profile)

    # Peakiness: ratio of max to mean in mid-frequencies (5-50 cycles)
    # High peakiness = regular geometric structures
    mid_freq = radial_profile[5:50]
    peakiness = float(mid_freq.max() / (mid_freq.mean() + 1e-10))

    # Directional energy: strong directional peaks = aligned structures
    # Check 4 principal directions in FFT
    angles = [0, 45, 90, 135]
    dir_energy = []
    for angle in angles:
        rad = np.radians(angle)
        line_sum = 0
        for dist in range(10, min(cy, cx)):
            py = int(cy + dist * np.sin(rad))
            px = int(cx + dist * np.cos(rad))
            if 0 <= py < magnitude.shape[0] and 0 <= px < magnitude.shape[1]:
                line_sum += magnitude[py, px]
        dir_energy.append(line_sum)

    dir_energy = np.array(dir_energy)
    directionality = float(dir_energy.max() / (dir_energy.mean() + 1e-10))

    results[f"exp5_{site}"] = {
        "peakiness": round(peakiness, 3),
        "directionality": round(directionality, 3),
        "dominant_angle": int(angles[np.argmax(dir_energy)]),
    }

    print(f"\n{site} ({SITE_TYPES[site]}):")
    print(f"  Spectral peakiness (regularity): {peakiness:.2f}")
    print(f"  Directionality: {directionality:.2f}")
    print(f"  Dominant angle: {angles[np.argmax(dir_energy)]}°")


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT 6: Super-Resolution Quality Assessment
# How much real information does 10m→2m upsampling add?
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("EXPERIMENT 6: Super-Resolution Information Content")
print("=" * 70)

for site in SITES:
    rgb = load_rgb(site)  # 2048px (2m/px interpolated from 10m)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Downsample to native 10m resolution (400px), then upsample back
    h, w = gray.shape
    native = cv2.resize(gray, (w // 5, h // 5), interpolation=cv2.INTER_AREA)  # →400px
    bicubic_up = cv2.resize(native, (w, h), interpolation=cv2.INTER_CUBIC)  # →2048 bicubic
    lanczos_up = cv2.resize(native, (w, h), interpolation=cv2.INTER_LANCZOS4)  # →2048 lanczos

    # SSIM between EE's 2048 (server-side interpolation) and our client-side
    ssim_bicubic = ssim(gray, bicubic_up)
    ssim_lanczos = ssim(gray, lanczos_up)

    # Information content: Laplacian variance (focus/sharpness metric)
    lap_ee = cv2.Laplacian(gray, cv2.CV_64F).var()
    lap_native = cv2.Laplacian(cv2.resize(native, (w, h)), cv2.CV_64F).var()
    lap_bicubic = cv2.Laplacian(bicubic_up, cv2.CV_64F).var()

    # Spatial frequency (gradient energy)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0).mean()**2
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1).mean()**2
    sf_ee = np.sqrt(gx + gy)

    gx_n = cv2.Sobel(bicubic_up, cv2.CV_64F, 1, 0).mean()**2
    gy_n = cv2.Sobel(bicubic_up, cv2.CV_64F, 0, 1).mean()**2
    sf_bicubic = np.sqrt(gx_n + gy_n)

    info_gain = (lap_ee - lap_bicubic) / (lap_bicubic + 1e-10) * 100

    results[f"exp6_{site}"] = {
        "ssim_bicubic": round(ssim_bicubic, 4),
        "ssim_lanczos": round(ssim_lanczos, 4),
        "laplacian_ee": round(float(lap_ee), 2),
        "laplacian_bicubic": round(float(lap_bicubic), 2),
        "info_gain_pct": round(float(info_gain), 1),
        "spatial_freq_ee": round(float(sf_ee), 4),
        "spatial_freq_bicubic": round(float(sf_bicubic), 4),
    }

    print(f"\n{site} ({SITE_TYPES[site]}):")
    print(f"  SSIM (EE vs bicubic): {ssim_bicubic:.4f}")
    print(f"  SSIM (EE vs lanczos): {ssim_lanczos:.4f}")
    print(f"  Laplacian variance: EE={lap_ee:.1f}, bicubic={lap_bicubic:.1f}")
    print(f"  Information gain from EE interpolation: {info_gain:+.1f}%")
    print(f"  Spatial frequency: EE={sf_ee:.4f}, bicubic={sf_bicubic:.4f}")


# ═══════════════════════════════════════════════════════════════════
# SYNTHESIS: What works, what doesn't
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("SYNTHESIS")
print("=" * 70)

# Save all results
output_path = os.path.join(os.path.dirname(__file__), "..", "methodology",
                           "FINDINGS.satellite-imagery.md")
with open("/tmp/research/experiment_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to /tmp/research/experiment_results.json")
print(f"Run complete. {len(results)} measurements across 6 experiments.")
