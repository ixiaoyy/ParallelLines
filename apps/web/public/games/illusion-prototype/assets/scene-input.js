(function (root) {
  'use strict';

  /**
   * Convert client coordinates into the same CSS-pixel space used by project().
   * rect is the canvas CSS bounding rect. No DPR multiplication or DOM mutation.
   */
  function cssPoint(clientX, clientY, rect) {
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  /**
   * Return displacement from pointerdown along one locked screen axis.
   * dx/dy are TOTAL client/CSS-pixel deltas from pointer.x/y, not event increments.
   * The first sample at least threshold pixels away locks pointer.dragAxis.
   * Positive means right for horizontal gestures, up for vertical gestures.
   * Only pointer.dragAxis is changed; game progress, limits and physics are untouched.
   */
  function dominantDelta(pointer, dx, dy, threshold) {
    const startDistance = threshold === undefined ? 6 : threshold;
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) return 0;
    if (pointer.dragAxis !== 'horizontal' && pointer.dragAxis !== 'vertical') {
      if (Math.hypot(dx, dy) < startDistance) return 0;
      pointer.dragAxis = Math.abs(dx) >= Math.abs(dy) ? 'horizontal' : 'vertical';
    }
    return pointer.dragAxis === 'horizontal' ? dx : -dy;
  }

  /**
   * Convert a locked CSS-pixel displacement into this control's scalar q units.
   * Add the result to the pointerdown q/angle snapshot; do NOT accumulate it again.
   * pixelsPerUnit is the existing per-control sensitivity. Angle callers multiply
   * by QUARTER explicitly; frame axes, q bounds, stops and snapping stay at call sites.
   */
  function rotationDelta(pointer, dx, dy, pixelsPerUnit, threshold) {
    if (!Number.isFinite(pixelsPerUnit) || pixelsPerUnit <= 0) return 0;
    return dominantDelta(pointer, dx, dy, threshold) / pixelsPerUnit;
  }

  /**
   * Preserve a linear control's physical projected axis (full q=0 to q=1 vector).
   * The returned value is a q displacement. A degenerate axis produces no jump.
   * This helper does not lock a screen axis or treat translation as rotation.
   */
  function projectedDelta(dx, dy, axisX, axisY) {
    if (![dx, dy, axisX, axisY].every(Number.isFinite)) return 0;
    const length2 = axisX * axisX + axisY * axisY;
    return length2 > 1e-8 ? (dx * axisX + dy * axisY) / length2 : 0;
  }

  root.IllusionSceneInput = Object.freeze({
    cssPoint: cssPoint,
    dominantDelta: dominantDelta,
    rotationDelta: rotationDelta,
    projectedDelta: projectedDelta
  });
})(typeof globalThis !== 'undefined' ? globalThis : window);
