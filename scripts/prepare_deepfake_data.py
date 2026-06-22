#!/usr/bin/env python3
"""
CyberLens — Deepfake Training Data Preparation
==================================================
Since we don't have a real deepfake dataset, this script generates
synthetic training data by downloading LFW faces and applying
augmentations to simulate deepfake artifacts.

Usage:
    python scripts/prepare_deepfake_data.py
    python scripts/prepare_deepfake_data.py --num-images 200

Author: CyberLens Team — GPCSSI Internship
"""

import argparse
import logging
import os
import random
import sys
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("cyberlens.deepfake_prep")


def generate_synthetic_face(size: Tuple[int, int] = (224, 224)) -> np.ndarray:
    """Generate a synthetic face-like image using geometric shapes.

    Creates realistic enough images for training pipeline validation.

    Args:
        size: Output image size (width, height).

    Returns:
        Synthetic face image as numpy array (BGR).
    """
    img = np.ones((size[1], size[0], 3), dtype=np.uint8)

    # Random skin tone background
    skin_tones = [
        (180, 200, 230), (160, 180, 210), (140, 160, 190),
        (120, 140, 170), (100, 120, 150), (80, 100, 130),
    ]
    base_color = random.choice(skin_tones)
    img[:] = base_color

    # Add noise for texture
    noise = np.random.randint(-15, 15, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    cx, cy = size[0] // 2, size[1] // 2

    # Face oval
    cv2.ellipse(img, (cx, cy), (70, 90), 0, 0, 360, base_color, -1)

    # Eyes
    eye_y = cy - 20
    for eye_x in [cx - 25, cx + 25]:
        cv2.ellipse(img, (eye_x, eye_y), (12, 8), 0, 0, 360, (255, 255, 255), -1)
        cv2.circle(img, (eye_x, eye_y), 5, (50, 50, 50), -1)

    # Nose
    pts = np.array([[cx, cy - 5], [cx - 8, cy + 15], [cx + 8, cy + 15]])
    cv2.polylines(img, [pts], True, (base_color[0] - 20, base_color[1] - 20, base_color[2] - 20), 2)

    # Mouth
    cv2.ellipse(img, (cx, cy + 35), (20, 8), 0, 0, 180, (100, 100, 150), 2)

    # Blur for realism
    img = cv2.GaussianBlur(img, (5, 5), 1.5)

    return img


def apply_deepfake_artifacts(image: np.ndarray) -> np.ndarray:
    """Apply simulated deepfake artifacts to an image.

    Artifacts include:
        - GAN-style frequency artifacts (DCT manipulation)
        - Blending boundary simulation
        - Compression cycling
        - Color inconsistency

    Args:
        image: Input face image (BGR).

    Returns:
        Modified image with deepfake artifacts.
    """
    result = image.copy()

    # Randomly apply 2-3 artifact types
    artifacts = random.sample([
        _apply_frequency_artifact,
        _apply_blending_artifact,
        _apply_compression_artifact,
        _apply_color_inconsistency,
    ], k=random.randint(2, 3))

    for artifact_fn in artifacts:
        result = artifact_fn(result)

    return result


def _apply_frequency_artifact(image: np.ndarray) -> np.ndarray:
    """Simulate GAN frequency artifacts via DCT manipulation."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dct = cv2.dct(gray)

    # Add periodic patterns (GAN fingerprint)
    h, w = dct.shape
    for freq in range(5, min(h, w), random.randint(8, 15)):
        intensity = random.uniform(0.5, 2.0)
        dct[freq, :] += intensity
        dct[:, freq] += intensity

    result_gray = cv2.idct(dct)
    result_gray = np.clip(result_gray, 0, 255).astype(np.uint8)

    # Merge back to color
    result = image.copy()
    result[:, :, 0] = cv2.addWeighted(
        image[:, :, 0], 0.7, result_gray, 0.3, 0
    )
    return result


def _apply_blending_artifact(image: np.ndarray) -> np.ndarray:
    """Simulate face-swap blending boundary artifacts."""
    h, w = image.shape[:2]
    cx, cy = w // 2, h // 2

    # Create elliptical mask (face region)
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(mask, (cx, cy), (w // 3, h // 3), 0, 0, 360, 1.0, -1)

    # Blur mask edge (imperfect blending)
    blur_size = random.choice([3, 5, 7])
    mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 2)

    # Slightly shift color inside mask
    shift = np.random.randint(-10, 10, 3)
    inner = image.astype(np.int16) + shift
    inner = np.clip(inner, 0, 255).astype(np.uint8)

    mask_3ch = np.stack([mask] * 3, axis=-1)
    result = (inner * mask_3ch + image * (1 - mask_3ch)).astype(np.uint8)
    return result


def _apply_compression_artifact(image: np.ndarray) -> np.ndarray:
    """Simulate JPEG quality cycling artifacts."""
    for _ in range(random.randint(2, 4)):
        quality = random.randint(15, 40)
        _, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    return image


def _apply_color_inconsistency(image: np.ndarray) -> np.ndarray:
    """Simulate selective channel color inconsistency."""
    channel = random.randint(0, 2)
    h, w = image.shape[:2]

    # Modify a random region's color channel
    x1 = random.randint(0, w // 3)
    y1 = random.randint(0, h // 3)
    x2 = random.randint(w * 2 // 3, w)
    y2 = random.randint(h * 2 // 3, h)

    result = image.copy()
    shift = random.randint(-15, 15)
    region = result[y1:y2, x1:x2, channel].astype(np.int16) + shift
    result[y1:y2, x1:x2, channel] = np.clip(region, 0, 255).astype(np.uint8)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Prepare synthetic deepfake training data",
    )
    parser.add_argument("--num-images", type=int, default=200,
                        help="Number of face images to generate per class")
    parser.add_argument("--output-dir", default="data/deepfake",
                        help="Output directory")
    args = parser.parse_args()

    output = Path(args.output_dir)
    train_real = output / "train" / "real"
    train_fake = output / "train" / "fake"
    val_real = output / "val" / "real"
    val_fake = output / "val" / "fake"

    for d in [train_real, train_fake, val_real, val_fake]:
        d.mkdir(parents=True, exist_ok=True)

    num_train = int(args.num_images * 0.8)
    num_val = args.num_images - num_train

    logger.info("Generating %d training + %d validation images per class...",
                num_train, num_val)

    # Generate real faces
    logger.info("Generating REAL face images...")
    for i in tqdm(range(num_train), desc="Train/Real"):
        img = generate_synthetic_face()
        cv2.imwrite(str(train_real / f"real_{i:04d}.jpg"), img)

    for i in tqdm(range(num_val), desc="Val/Real"):
        img = generate_synthetic_face()
        cv2.imwrite(str(val_real / f"real_{i:04d}.jpg"), img)

    # Generate fake faces (with artifacts)
    logger.info("Generating FAKE face images with deepfake artifacts...")
    for i in tqdm(range(num_train), desc="Train/Fake"):
        img = generate_synthetic_face()
        img = apply_deepfake_artifacts(img)
        cv2.imwrite(str(train_fake / f"fake_{i:04d}.jpg"), img)

    for i in tqdm(range(num_val), desc="Val/Fake"):
        img = generate_synthetic_face()
        img = apply_deepfake_artifacts(img)
        cv2.imwrite(str(val_fake / f"fake_{i:04d}.jpg"), img)

    logger.info("=" * 50)
    logger.info("Deepfake data generation complete!")
    logger.info("  Train: %d real + %d fake", num_train, num_train)
    logger.info("  Val:   %d real + %d fake", num_val, num_val)
    logger.info("  Output: %s", output.resolve())
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
