#!/usr/bin/env python3
"""
Deep diagnostic script to test why diagrams are still enrolling.
This script will:
1. Check environment variables in staging
2. Test the v2 likeness gate locally with a synthetic diagram
3. Simulate the exact flow through model-service endpoints
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from app.engines.fingerprint_engine_v2 import FingerprintEngineV2
from app.core.config import (
    FINGERPRINT_V2_LIKENESS_THRESHOLD,
    FINGERPRINT_V2_MIN_COVERAGE,
    FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY,
    FINGERPRINT_V2_MIN_KP_COUNT,
    FINGERPRINT_V2_MIN_KP_SPREAD,
    FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO,
    FINGERPRINT_V2_MAX_TILE_COVERAGE_STD,
    FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT,
    FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO,
    FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO,
    FINGERPRINT_V2_MIN_MEAN_PERIODICITY,
    FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO,
    FINGERPRINT_V2_QUALITY_THRESHOLD,
)
from model_service.main import _v2_likeness_verdict

def create_diagram():
    """Create a synthetic sad-face diagram like the one that's enrolling."""
    img = np.ones((256, 256), dtype=np.uint8) * 255
    
    # Draw sad face
    cv2.circle(img, (128, 128), 80, 0, 2)  # head
    cv2.circle(img, (105, 110), 8, 0, -1)  # left eye
    cv2.circle(img, (151, 110), 8, 0, -1)  # right eye
    
    # Sad mouth (upside-down arc)
    cv2.ellipse(img, (128, 155), (30, 20), 0, 0, 180, 0, 2)
    
    return img

def print_threshold_config():
    """Print all configured thresholds."""
    print("\n" + "="*80)
    print("FINGERPRINT V2 THRESHOLDS (from environment or defaults)")
    print("="*80)
    print(f"Likeness Score Threshold:              {FINGERPRINT_V2_LIKENESS_THRESHOLD}")
    print(f"Min Coverage:                          {FINGERPRINT_V2_MIN_COVERAGE}")
    print(f"Min Orientation Entropy:               {FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY}")
    print(f"Min Keypoint Count:                    {FINGERPRINT_V2_MIN_KP_COUNT}")
    print(f"Min Keypoint Spread:                   {FINGERPRINT_V2_MIN_KP_SPREAD}")
    print(f"Min Tile Active Ratio:                 {FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO}")
    print(f"Max Tile Coverage Std Dev:             {FINGERPRINT_V2_MAX_TILE_COVERAGE_STD}")
    print(f"Min Edge Component Count:              {FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT}")
    print(f"Max Largest Edge Component Ratio:      {FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO}")
    print(f"Min Periodic Tile Ratio:               {FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO}")
    print(f"Min Mean Periodicity:                  {FINGERPRINT_V2_MIN_MEAN_PERIODICITY}")
    print(f"Min Ridge Block Ratio:                 {FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO}")
    print(f"Quality Score Threshold:               {FINGERPRINT_V2_QUALITY_THRESHOLD}")
    print("="*80)

def test_diagram_rejection():
    """Test that the diagram is properly rejected by v2 likeness gates."""
    print("\n" + "="*80)
    print("TESTING SYNTHETIC DIAGRAM REJECTION")
    print("="*80)
    
    engine = FingerprintEngineV2()
    diagram = create_diagram()
    
    # Get likeness components
    likeness = engine.fingerprint_likeness_components(diagram)
    
    print("\nDiagram Likeness Components:")
    print(f"  Likeness Score:                   {likeness.get('score', 0):.4f}")
    print(f"  Coverage:                         {likeness.get('coverage', 0):.4f}")
    print(f"  Orientation Entropy:              {likeness.get('orientation_entropy', 0):.4f}")
    print(f"  Keypoint Count:                   {likeness.get('kp_count', 0)}")
    print(f"  Keypoint Spread:                  {likeness.get('kp_spread', 0):.4f}")
    print(f"  Tile Active Ratio:                {likeness.get('tile_active_ratio', 0):.4f}")
    print(f"  Tile Coverage Std Dev:            {likeness.get('tile_coverage_std', 0):.4f}")
    print(f"  Edge Component Count:             {likeness.get('edge_component_count', 0)}")
    print(f"  Largest Edge Component Ratio:     {likeness.get('largest_edge_component_ratio', 1):.4f}")
    print(f"  Periodic Tile Ratio:              {likeness.get('periodic_tile_ratio', 0):.4f}")
    print(f"  Mean Periodicity:                 {likeness.get('mean_periodicity', 0):.4f}")
    print(f"  Ridge Block Ratio:                {likeness.get('ridge_block_ratio', 0):.4f}")
    print(f"  Line Count:                       {likeness.get('line_count', 0)}")
    print(f"  Circle Count:                     {likeness.get('circle_count', 0)}")
    
    # Check current model-service verdict logic
    print("\nGate Validation:")
    ok_like, reasons = _v2_likeness_verdict(likeness)
    failures = list(reasons)
    
    score = float(likeness.get('score', 0))
    if score >= FINGERPRINT_V2_LIKENESS_THRESHOLD:
        print(f"✓ Likeness score: {score:.4f} >= {FINGERPRINT_V2_LIKENESS_THRESHOLD}")
    
    coverage = float(likeness.get('coverage', 0))
    if coverage >= FINGERPRINT_V2_MIN_COVERAGE:
        print(f"✓ Coverage: {coverage:.4f} >= {FINGERPRINT_V2_MIN_COVERAGE}")
    
    entropy = float(likeness.get('orientation_entropy', 0))
    if entropy >= FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY:
        print(f"✓ Orientation entropy: {entropy:.4f} >= {FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY}")
    
    kp_count = int(likeness.get('kp_count', 0))
    if kp_count >= FINGERPRINT_V2_MIN_KP_COUNT:
        print(f"✓ Keypoint count: {kp_count} >= {FINGERPRINT_V2_MIN_KP_COUNT}")
    
    kp_spread = float(likeness.get('kp_spread', 0))
    if kp_spread >= FINGERPRINT_V2_MIN_KP_SPREAD:
        print(f"✓ Keypoint spread: {kp_spread:.4f} >= {FINGERPRINT_V2_MIN_KP_SPREAD}")
    
    tile_active = float(likeness.get('tile_active_ratio', 0))
    if tile_active >= FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO:
        print(f"✓ Tile active ratio: {tile_active:.4f} >= {FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO}")
    
    tile_std = float(likeness.get('tile_coverage_std', 0))
    if tile_std <= FINGERPRINT_V2_MAX_TILE_COVERAGE_STD:
        print(f"✓ Tile coverage std: {tile_std:.4f} <= {FINGERPRINT_V2_MAX_TILE_COVERAGE_STD}")
    
    edge_count = int(likeness.get('edge_component_count', 0))
    if edge_count >= FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT:
        print(f"✓ Edge component count: {edge_count} >= {FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT}")
    
    edge_ratio = float(likeness.get('largest_edge_component_ratio', 1))
    if edge_ratio <= FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO:
        print(f"✓ Largest edge component ratio: {edge_ratio:.4f} <= {FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO}")
    
    periodic_tile = float(likeness.get('periodic_tile_ratio', 0))
    if periodic_tile >= FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO:
        print(f"✓ Periodic tile ratio: {periodic_tile:.4f} >= {FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO}")
    
    periodicity = float(likeness.get('mean_periodicity', 0))
    if periodicity >= FINGERPRINT_V2_MIN_MEAN_PERIODICITY:
        print(f"✓ Mean periodicity: {periodicity:.4f} >= {FINGERPRINT_V2_MIN_MEAN_PERIODICITY}")
    
    ridge_block = float(likeness.get('ridge_block_ratio', 0))
    if ridge_block >= FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO:
        print(f"✓ Ridge block ratio: {ridge_block:.4f} >= {FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO}")
    
    # Quality score
    quality = engine.quality_score(diagram)
    if quality >= FINGERPRINT_V2_QUALITY_THRESHOLD:
        print(f"✓ Quality score: {quality:.4f} >= {FINGERPRINT_V2_QUALITY_THRESHOLD}")
    else:
        failures.append("reject_quality")
    
    print("\n" + "-"*80)
    if failures:
        print("RESULT: ❌ Diagram SHOULD BE REJECTED")
        print("\nFailure Reasons (model verdict):")
        for failure in failures:
            print(f"  {failure}")
        return False
    else:
        print("RESULT: ⚠️  Diagram WOULD PASS (all gates passed - THIS IS THE PROBLEM!)")
        return True

if __name__ == "__main__":
    print_threshold_config()
    passes = test_diagram_rejection()
    
    if passes:
        print("\n" + "="*80)
        print("⚠️  CRITICAL FINDING: The synthetic diagram PASSES all v2 gates locally!")
        print("="*80)
        print("\nThis means one of the following:")
        print("1. The thresholds in .env are still using defaults (too lenient)")
        print("2. The Cloud Run model-service is not receiving the new thresholds")
        print("3. The actual user diagram is DIFFERENT from our synthetic test")
        print("4. There's a bug in the likeness component calculation")
        print("\nNext steps:")
        print("- Check that .env is being read correctly")
        print("- Verify Cloud Run deployment status and env vars")
        print("- Request user to upload the ACTUAL diagram for testing")
        print("- Check logs in Cloud Run to see what thresholds model-service is using")
    else:
        print("\n" + "="*80)
        print("✓ GOOD NEWS: The synthetic diagram is properly rejected locally.")
        print("="*80)
        print("\nThis means the code logic is correct. The issue must be:")
        print("1. Cloud Run model-service is running OLD code (not feee02e)")
        print("2. Cloud Run model-service is not receiving environment variables")
        print("3. User is hitting the LEGACY /enroll/fingerprint endpoint instead of /experimental/enroll/fingerprint")
        print("4. There's a network/deployment issue")
        print("\nNext steps:")
        print("- Check Cloud Run service revision and environment variables")
        print("- Capture network traffic from user to see which endpoint is being called")
        print("- Check if legacy route is still being called somehow")
