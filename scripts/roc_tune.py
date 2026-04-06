import os
import sys
import csv
import argparse
import cv2
import numpy as np


def import_engine():
    # Ensure repo root on path so `app` is importable when script run from scripts/
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from app.engines.fingerprint_engine import fingerprint_score_components
        return fingerprint_score_components
    except Exception as e:
        raise ImportError(f"Failed to import fingerprint engine: {e}")


def gather_scores(folder, label, scorer, allowed_exts=None):
    rows = []
    allowed_exts = allowed_exts or {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
    for root, _, files in os.walk(folder):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in allowed_exts:
                continue
            path = os.path.join(root, f)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"warning: failed to read {path}")
                continue
            try:
                comps = scorer(img)
            except Exception as e:
                print(f"warning: scorer failed for {path}: {e}")
                continue
            row = {
                'path': path,
                'label': int(label),
                'score': float(comps.get('score', 0.0)),
                'score_coh': float(comps.get('score_coh', 0.0)),
                'score_fft': float(comps.get('score_fft', 0.0)),
                'score_edge': float(comps.get('score_edge', 0.0)),
                'score_grad': float(comps.get('score_grad', 0.0)),
            }
            rows.append(row)
    return rows


def write_csv(rows, out_path):
    fieldnames = ['path', 'label', 'score', 'score_coh', 'score_fft', 'score_edge', 'score_grad']
    with open(out_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def compute_roc(scores, labels):
    # scores: numpy array, labels: 0/1
    # Compute FPR, TPR for thresholds derived from scores
    desc_order = np.argsort(-scores)
    labels_sorted = labels[desc_order]
    scores_sorted = scores[desc_order]
    P = labels.sum()
    N = len(labels) - P
    tprs = []
    fprs = []
    thresholds = []
    tp = 0
    fp = 0
    prev_score = None
    for s, l in zip(scores_sorted, labels_sorted):
        if prev_score is None:
            prev_score = s
        if s != prev_score:
            tprs.append(tp / P if P > 0 else 0.0)
            fprs.append(fp / N if N > 0 else 0.0)
            thresholds.append(prev_score)
            prev_score = s
        if l == 1:
            tp += 1
        else:
            fp += 1
    # final point
    tprs.append(tp / P if P > 0 else 0.0)
    fprs.append(fp / N if N > 0 else 0.0)
    thresholds.append(prev_score)
    # Compute AUC via trapezoid over FPR ascending
    fprs_arr = np.array(fprs)
    tprs_arr = np.array(tprs)
    # sort by fpr ascending
    order = np.argsort(fprs_arr)
    f = fprs_arr[order]
    t = tprs_arr[order]
    auc = np.trapz(t, f)
    return {'fpr': f, 'tpr': t, 'thresholds': np.array(thresholds)[order], 'auc': auc}


def recommend_threshold(roc, target_spec=0.95):
    # find threshold with fpr <= (1-target_spec)
    f = roc['fpr']
    t = roc['tpr']
    thr = roc['thresholds']
    max_fpr = 1.0 - target_spec
    idx = np.where(f <= max_fpr)[0]
    if len(idx) == 0:
        # no threshold meets specificity target; return highest specificity point
        best = np.argmin(f)
    else:
        # pick threshold maximizing TPR while satisfying specificity
        candidate = idx[np.argmax(t[idx])]
        best = candidate
    return {'threshold': float(thr[best]), 'fpr': float(f[best]), 'tpr': float(t[best])}


def main():
    parser = argparse.ArgumentParser(description='Collect fingerprint-likeness scores and compute ROC')
    parser.add_argument('--pos', required=True, help='Folder with positive (real fingerprint) images')
    parser.add_argument('--neg', required=True, help='Folder with negative (non-fingerprint) images')
    parser.add_argument('--out', default='fp_scores.csv', help='CSV output path')
    parser.add_argument('--spec', type=float, default=0.95, help='Target specificity for recommended threshold')
    args = parser.parse_args()

    scorer = import_engine()
    print('scanning positives...')
    pos_rows = gather_scores(args.pos, 1, scorer)
    print('scanning negatives...')
    neg_rows = gather_scores(args.neg, 0, scorer)
    rows = pos_rows + neg_rows
    if not rows:
        print('no images found or scoring failed')
        return
    write_csv(rows, args.out)
    scores = np.array([r['score'] for r in rows])
    labels = np.array([r['label'] for r in rows])
    roc = compute_roc(scores, labels)
    rec = recommend_threshold(roc, target_spec=args.spec)
    print(f"AUC: {roc['auc']:.4f}")
    print(f"Recommended threshold for specificity {args.spec:.2f}: {rec['threshold']:.4f} (FPR={rec['fpr']:.4f}, TPR={rec['tpr']:.4f})")
    print(f"CSV written to: {args.out} (rows={len(rows)})")


if __name__ == '__main__':
    main()
