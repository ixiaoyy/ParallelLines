**Source visual truth**

- `C:/Users/phpxi/AppData/Local/Temp/codex-clipboard-524c9552-f21c-4f78-8cdd-11f650ec809a.png`
- Production source asset: `static/web/private-space-entry.png`
- Production CDN URL: `https://img.pingxingxian.space/static/web/private-space-entry.png`
- Source dimensions: 1660 × 948; optimized production dimensions: 1024 × 388.

**Implementation evidence**

- Full page: `C:/Users/phpxi/AppData/Local/Temp/private-space-home-implementation.png`
- Focused card crop: `C:/Users/phpxi/AppData/Local/Temp/private-space-entry-crop.png`
- Side-by-side comparison: `C:/Users/phpxi/AppData/Local/Temp/private-space-entry-comparison.png`
- Viewport: 1280 × 720 desktop, device pixel ratio 2.
- State: local home page with the admin-only prop temporarily enabled for visual inspection; the prop was restored to the real `canDeleteTopics` permission gate afterward.

**Full-view comparison evidence**

- The card renders beneath the existing left navigation panel using the optimized banner ratio.
- The crop keeps the complete entry sign and both characters' faces while removing excess top and lower foreground.
- The surrounding home layout is unchanged.

**Focused region comparison evidence**

- The rendered image uses the production crop without any additional browser-side stretching or clipping.
- The deployed image dimensions are 1024 × 388.

**Findings**

- Fonts and typography: passed. The private-space entry lettering remains part of the selected raster artwork; no replacement web font or duplicate HTML copy is present.
- Spacing and layout rhythm: passed. The card uses the source aspect ratio with no clipping or stretching and keeps the existing 1rem rail gap.
- Colors and visual tokens: passed. The bright pink-purple source colors are preserved; CSS only supplies a matching fallback surface, focus ring, and subtle interaction shadow.
- Image quality and asset fidelity: passed. The original generated PNG is used directly and remains sharp at the rendered size.
- Copy and content: passed. All visible entry copy comes from the selected artwork; no duplicate HTML copy remains in the component.
- Interaction and accessibility: passed. The whole image is one link, its accessible label identifies the private space, keyboard focus remains visible, and click navigation reached `/b/private-space`.
- Permission state: passed. After restoring the real permission gate, the signed-out browser rendered zero private-space links.

**Comparison history**

- Initial implementation: no P0/P1/P2 mismatches found in the focused comparison.
- Final verification: updated intrinsic dimensions and the rendered ratio to the optimized 1024 × 388 production crop.

**Implementation Checklist**

- [x] Use the selected image as the complete visual asset.
- [x] Remove old lock, administrator label, and planning subtitle.
- [x] Preserve admin-only visibility and private-space navigation.
- [x] Verify crop, ratio, image load, focus treatment, click navigation, and signed-out hiding.

**Follow-up Polish**

- None required for the selected design.

final result: passed
