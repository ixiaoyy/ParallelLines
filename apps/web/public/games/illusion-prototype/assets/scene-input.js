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

  /** Keep two-finger gestures native; cancel game input until every touch stream ends. */
  function installPinchGuard(surface) {
    const doc = surface.ownerDocument, view = doc.defaultView, touches = new Map();
    let multi = false, cancelling = false, suppressClick = false;
    const cancelGameTouches = () => {
      cancelling = true;
      try {
        for (const [pointerId, touch] of touches) touch.target.dispatchEvent(new view.PointerEvent('pointercancel', {
          bubbles: true, pointerId: pointerId, pointerType: 'touch', clientX: touch.x, clientY: touch.y
        }));
      } finally { cancelling = false; }
    };
    const clear = () => { if (touches.size) suppressClick = true; cancelGameTouches(); touches.clear(); multi = false; };
    const track = event => {
      if (cancelling) return;
      if (multi && event.pointerType !== 'touch') { event.stopImmediatePropagation(); return; }
      if (event.type === 'pointerdown') {
        if (event.pointerType !== 'touch') { if (!touches.size) suppressClick = false; return; }
        if (!surface.contains(event.target) && !touches.size) return;
        if (!touches.size) suppressClick = false;
        touches.set(event.pointerId, { target: event.target, x: event.clientX, y: event.clientY });
        if (touches.size > 1 && !multi) { multi = true; suppressClick = true; cancelGameTouches(); }
      }
      if (!touches.has(event.pointerId)) {
        if (event.pointerType === 'touch' && surface.contains(event.target) && ['pointerup', 'pointercancel', 'lostpointercapture'].includes(event.type)) event.stopImmediatePropagation();
        return;
      }
      if (multi) event.stopImmediatePropagation();
      if (event.type === 'pointerup' || event.type === 'pointercancel') {
        touches.delete(event.pointerId);
        if (!touches.size) multi = false;
      }
    };
    for (const type of ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'lostpointercapture']) {
      view.addEventListener(type, track, { capture: true, passive: true });
    }
    // Suppress a compatibility click from the cancelled gesture, never its native pinch default.
    view.addEventListener('click', event => {
      if (suppressClick && surface.contains(event.target) && (event.detail !== 0 || event.pointerType === 'touch' || event.sourceCapabilities?.firesTouchEvents)) {
        event.preventDefault(); event.stopImmediatePropagation();
      }
    }, { capture: true });
    view.addEventListener('blur', clear);
    view.addEventListener('pagehide', clear);
    doc.addEventListener('visibilitychange', () => { if (doc.hidden) clear(); });
  }

  root.IllusionSceneInput = Object.freeze({
    cssPoint: cssPoint,
    dominantDelta: dominantDelta,
    rotationDelta: rotationDelta,
    projectedDelta: projectedDelta,
    installPinchGuard: installPinchGuard
  });
  const surface = root.document?.querySelector('.prototype');
  if (surface) installPinchGuard(surface);
})(typeof globalThis !== 'undefined' ? globalThis : window);
