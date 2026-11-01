# MK3 instrument illustrations

Created with the built-in Imagegen tool. Original generated images are retained under `output/imagegen/mk3-instruments/*-source.png`; native display assets below preserve alpha and fit 448 × 120 pixels. No logos or third-party product depictions were requested.

The first OUTPUT display selects its illustration from the current Sound. Samples keep the waveform, instruments use their synth image, effects use the filter image, and empty Sounds show no artwork. The right OUTPUT routing grid is unchanged. Images are decoded once in the isolated display renderer, never in the audio/input path.

## Machinista Synth

Asset: [machinista-synth.png](machinista-synth.png)

Final prompt:

> Create one production UI bitmap asset for a 480x272-pixel groovebox display, not a screenshot or UI mockup. Subject: an original compact Machinista software synthesizer represented as a beautiful small physical desktop keyboard synth, viewed slightly from above, centered, almost front-on. Wide horizontal silhouette, about 3.2:1, full device visible with generous clean transparent padding. Matte charcoal body, vivid orange illuminated accents, four clearly separated oscillator sections with four tiny simple waveform screens, a few large rotary knobs, short 2-octave piano keyboard. Strong clear geometry and crisp edges that remain legible when the whole object is displayed only 420 pixels wide and 112 pixels high. Refined restrained 3D product illustration with soft bevels, small highlights, strong contrast; not photoreal clutter, not cartoon. Absolutely no text, no letters, no numbers, no brand marks, no cables, no hands, no external props. Genuine transparent background including outside the object and no baked checkerboard, no scene or floor. Output a single isolated synth only.

## Generic instrument

Asset: [generic-synth.png](generic-synth.png)

Final prompt:

> Create one isolated production UI bitmap asset for a tiny 480x272 groovebox display. A generic original analog synthesizer keyboard, matte charcoal body with cyan-blue illuminated accents, two simple oscillator panels, several large knobs, short 2-octave piano keys. Wide low horizontal silhouette about 3.2:1, centered, full device visible, slightly elevated almost front-on product view. Crisp restrained 3D product illustration, soft bevels and highlights, strong simple geometry that reads clearly when displayed at only 420 pixels wide by 112 high. No text, no letters, no numbers, no logos, no brand references, no cables, no people or props. Truly transparent background, no floor, no scene, no baked checkerboard. Single synthesizer only.

## Filter / effect

Asset: [generic-filter.png](generic-filter.png)

Final prompt:

> Create one isolated production UI bitmap asset for a tiny 480x272 groovebox display: an original compact stereo filter/effect desktop module with a matte charcoal metal body, two very large rotary knobs, three smaller controls, and one wide luminous yellow-orange screen showing a simple resonant low-pass filter response curve. Clearly looks like an audio filter/effect, not a keyboard. Wide horizontal silhouette about 3.2:1, centered, whole module visible, slightly elevated almost front-on view. Refined restrained 3D product illustration with crisp edges, small highlights, bold simple geometry, legible when shown at 420 pixels wide and 112 high. Purple and amber/orange small accents. No text, letters, numbers, brand marks, cables, hands or external objects. Genuine transparent background; no environment, no floor, no baked checkerboard. One filter/effect module only.

## Keyboard correction — 1 November 2026

The two keyboard illustrations were edited with built-in Imagegen. Both now use
a 25-key C-to-C keyboard: 15 white keys and 10 black keys in groups 2–3–2–3,
with no black key between E/F or B/C. The orange Machinista Synth has an **MS**
housing badge. The filter illustration is unchanged.

Exact edit prompts: [edit-prompts-20261101.json](edit-prompts-20261101.json).
High-resolution edited sources are retained locally under
`output/imagegen/synth-keyboards-20261101/`; the two PNGs in this folder are the
production 448 × 120 RGBA assets. Preparation only crops transparent outer padding
and scales the generated artwork; it does not redraw keys or lettering.

## Machinista native effects — 1 November 2026

Each native effect and Ducktor has its own generated machine illustration:
EQ, Compressor, Limiter, Transient, Reverb, Delay, Chorus, Flanger, Phaser,
Tremolo, Vibrato, Auto Pan and Ducktor. These use the `fx-*.png` files here,
all 448 × 120 RGBA, and are selected by exact effect URI in Channel and in
the first Plugin-chain page. They share charcoal metal, copper/brass machinery
and orange illumination with small cyan accents. Unrelated external plug-ins
retain their generic fallback.

Created with built-in Imagegen; exact prompts are in
[native-effects-prompts.json](native-effects-prompts.json). High-resolution source
images are saved locally under `output/imagegen/native-effects-20261101/`.
Only transparent padding crop and proportional downscaling follow generation.
