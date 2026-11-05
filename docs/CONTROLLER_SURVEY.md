# Controller Lab

Help add support for another controller without installing a test app.

**Open [Controller Lab](https://photogeen.github.io/machinista/controller-survey/) in desktop Chrome or Edge.** Connect the controller to that computer by USB. A controller connected to a Pi is not reachable from a browser running on a different computer.

## For testers

1. Close music applications using the controller. Choose its exact model in Controller Lab.
2. Select **Connect USB controller** and allow access to the NI device. Some devices expose more than one HID interface: use **Add HID interface** if some controls produce no data.
3. For a keyboard, open **MIDI inputs → Find MIDI inputs**. Choose only the input ports belonging to this keyboard. Matching names are suggested. Ports must already be available to the operating system; the website cannot install a USB-MIDI driver.
4. Follow each prompt. Click **Record this control**, keep still for one second, operate only the named control during the next four seconds, then release it. Confirm the action and continue. Each rotary control has separate clockwise and counterclockwise tests. Every physical key has its own test.
5. If a control sends no data, leave it untested and add a short observation. Do not confirm unrelated input. The control selector lets you return to any test. Use **Missing a physical control?** to add controls not listed. A secondary SHIFT label does not count as another physical button.
6. Compare the complete list with the actual hardware, then tick the layout check. The review section lists every required action still missing. A partial report is useful; it is never labelled a completed physical input check.
7. **Open Discord channel** downloads the JSON and opens the [Machinista community](https://discord.gg/3B8mQMyQR). Choose **#controllers** and attach the file there yourself (Discord sign-in may be required). The invitation currently opens #general first; switch to #controllers before posting. Alternatively, **Download JSON** to save your measurements. **Prepare email** also downloads the file and opens a draft in your mail app. **Attach the downloaded JSON yourself**, then send. Send to **machinista@photogeen.com**. You can also use webmail. The browser cannot add a mail attachment automatically.

Progress is saved in this browser when storage is available. Keep a downloaded copy too. **Resume saved JSON** can restore it later. Resume only on the same physical controller, with the same octave, MIDI and transpose settings. If the controller disconnects or the page is hidden, repeat the interrupted test. Do not use demo measurements as hardware evidence.

No serial numbers, USB paths, MIDI port names or host names are included in browser exports. Observations are plain text: do not put personal information in them. Emailing is manual; nothing is automatically uploaded to GitHub. By submitting, testers agree to publication of the measurement file under GPL-3.0-or-later. Downloading a private backup does not require publication consent.

## Models and limits

The model selector includes only controllers still needing integration: Maschine Studio, Jam, Mikro MK3; Komplete Kontrol S-Series MK1/MK2/MK3, A25/A49/A61 and M32. Model selection describes the planned checklist, **not existing Machinista support**. Already supported MK1/MK2/MK3, Maschine+, Mikro MK1/MK2 are excluded from new surveys. Historical measurement files remain reviewable. Sources are linked per model in the assistant. Physical layouts and report decoding still require tester/maintainer review. Missing controls can be added before submission.

This first browser version records inputs. **LEDs, displays, USB audio, DIN MIDI sockets and live driver behaviour are not verified.** Native buttons often use HID rather than MIDI. Browser/OS permissions or an NI background service may prevent access, and some hardware may need an initialization sequence not yet known. Do not replace system drivers or firmware for this test. Report the failure instead.

Safari and Firefox do not provide the same WebHID access as desktop Chrome/Edge. Linux may require HID device permissions. A web page cannot bypass those restrictions. No HID output or feature report is sent by this version; it does not alter firmware or the installed Machinista project.

## For maintainers

Browser source: `web/controller-survey/`. Shared hardware inventory: `app/controller_survey_catalog.py`; regenerate the browser copy with `python3 tools/build_controller_survey_catalog.py`. Discord link: `web/controller-survey/config.json` → `discordUrl`. Public email address: `web/controller-survey/config.json` → `submissionEmail`. Do not put mail passwords or API keys there. GitHub Pages hosts the site beside the existing manuals.

Review a received file with:

```sh
python3 tools/review_controller_survey.py received-survey.json --output controller-review.json
```

The importer validates identity, limits and raw evidence and derives possible mappings. It never executes a submitted mapping, installs a driver or activates hardware support. Encoder decoding, pad thresholds/crosstalk, outputs and timing need separate implementation and hardware checks. Browser `tester_confirmed` means the tester performed the action, not that a candidate mapping was independently verified. The review file always has `activation_allowed: false`.

Only after checking the file and publication consent, add it under `controller-surveys/<profile-id>/`. These files are evidence, not runtime configuration. Do not include email headers or personal information.

Checks:

```sh
node --test tests/controller-survey/core.test.mjs
python3 -m unittest tests.test_controller_survey
```

## Reference material

Inventories use the controller manufacturers' hardware references, with labels normalized to distinguish physical controls. No manufacturer manual artwork is distributed with this tool.

- [NI manual archive](https://www.native-instruments.com/pages/maschine-downloads)
- [Maschine Studio manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/maschine_276/MASCHINE_2.0_STUDIO_2.7.6_0518_Manual_English.pdf)
- [Maschine Jam manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/maschine_278/MASCHINE_JAM_Manual_English_2_7_8.pdf)
- [Mikro MK3 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/maschine_2_8/MASCHINE_2.0_MIKRO_MK3_Manual_English_2_8.pdf)
- [Komplete Kontrol S MK1 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_S-Series_MK1_1.9.2_1217_Manual_English.pdf)
- [Komplete Kontrol S MK2 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_S-Series_MK2_202_Manual_English.pdf)
- [Kontrol S MK3 keyboard overview](https://docs.native-instruments.com/online-guides/kontrol-s-mk3-manual/en/keyboard-overview.html)
- [A-Series manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_A-Series_Manual_English_04_2022.pdf)
- [M32 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_M32_Manual_English_28_10_2021.pdf)
- [WebHID browser API](https://developer.chrome.com/docs/capabilities/hid)
- [Web MIDI browser API](https://developer.mozilla.org/en-US/docs/Web/API/Web_MIDI_API)
