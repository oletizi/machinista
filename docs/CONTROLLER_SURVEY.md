# Controller Lab

Help add support for another controller without installing a test app.

**Open [Controller Lab](https://photogeen.github.io/machinista/controller-survey/) in desktop Chrome or Edge.** Connect the controller to that computer by USB. A controller connected to a Pi is not reachable from a browser running on a different computer.

## For testers

1. Close music applications using the controller. Choose its exact model in Controller Lab.
2. Select **Connect USB controller** and allow access to the NI device. Some devices expose more than one HID interface: use **Add HID interface** if some controls produce no data.
3. For a keyboard, open **MIDI inputs → Find MIDI inputs**. Choose only the input ports belonging to this keyboard. Matching names are suggested. Ports must already be available to the operating system; the website cannot install a USB-MIDI driver.
4. Follow each prompt. Click **Record this control**, keep still for one second, operate only the named control during the next four seconds, then release it. Confirm the action and continue. Each rotary control has separate clockwise and counterclockwise tests. Every physical key has its own test.
5. If a control sends no data, leave it untested and add a short observation. Do not confirm unrelated input. The control selector lets you return to any test. Use **Missing a physical control?** to add controls not listed. A secondary SHIFT label does not count as another physical button.
6. Open **Check every display**. Choose each physical display in turn, enable the fixed test images, and send **Border**, **Grid** and **Colors / brightness**. Compare each image with the preview and choose **Matches preview** only when it is actually visible and correct. Record no image, cropped content, wrong orientation or colors with **Incorrect / no image**. If the browser cannot access a known interface, or a protocol is not implemented, the result remains blocked. Then compare the input checklist with the actual hardware and tick the layout check. The review section lists every required action still missing. A partial report is useful; it is never labelled a completed physical input check.
7. **Open Discord channel** downloads the JSON and opens the [Machinista community](https://discord.gg/3B8mQMyQR). Choose **#controllers** and attach the file there yourself (Discord sign-in may be required). The invitation currently opens #general first; switch to #controllers before posting. Alternatively, **Download JSON** to save your measurements. **Prepare email** also downloads the file and opens a draft in your mail app. **Attach the downloaded JSON yourself**, then send. Send to **machinista@photogeen.com**. You can also use webmail. The browser cannot add a mail attachment automatically.

Progress is saved in this browser when storage is available. Keep a downloaded copy too. **Resume saved JSON** can restore it later. Resume only on the same physical controller, with the same octave, MIDI and transpose settings. If the controller disconnects or the page is hidden, repeat the interrupted test. Do not use demo measurements as hardware evidence.

No serial numbers, USB paths, MIDI port names or host names are included in browser exports. Observations are plain text: do not put personal information in them. Emailing is manual; nothing is automatically uploaded to GitHub. By submitting, testers agree to publication of the measurement file under GPL-3.0-or-later. Downloading a private backup does not require publication consent.

## Models and limits

The model selector includes only controllers still needing integration: Maschine Studio, Jam, Mikro MK3; Komplete Kontrol S-Series MK1/MK2/MK3, A25/A49/A61 and M32. Model selection describes the planned checklist, **not existing Machinista support**. Already supported MK1/MK2/MK3, Maschine+, Mikro MK1/MK2 are excluded from new surveys. Historical measurement files remain reviewable. Sources are linked per model in the assistant. Physical layouts and report decoding still require tester/maintainer review. Missing controls can be added before submission.

The browser records inputs and includes a separate inventory and three-image test for every display on the offered controllers. Maschine Jam has no bitmap display. Studio and S-Series MK2 have two color displays; S-Series MK1 has eight individual OLEDs; Mikro MK3, A-Series and M32 have one OLED each. Kontrol S-Series MK3 has a wide color display but uses a different ODR protocol: its display is included as **blocked / protocol not implemented**, not marked passed.

Known monochrome output uses WebHID and checks the device identity and declared report length before writing. Studio/S-MK2 color output uses WebUSB; choose the same controller in the second permission dialog. Connect only one controller of the same model during this test. Only the known vendor display interface and endpoint are claimed, never audio/MIDI/firmware interfaces. No driver is detached and no USB configuration is changed. On some Mac/Windows/Linux setups the OS or NI service prevents exclusive access. A correct test packet does not guarantee a working physical display until a tester confirms the result.

**LEDs, USB audio, DIN MIDI sockets and live driver behaviour are not verified.** Native buttons often use HID rather than MIDI. Browser/OS permissions or an NI background service may prevent access, and some hardware may need an initialization sequence not yet known. Do not replace system drivers or firmware for this test. Report the failure instead.

Safari and Firefox do not provide the same WebHID access as desktop Chrome/Edge. Linux may require HID device permissions. A web page cannot bypass those restrictions. Only the fixed, model-specific display test packets are sent after enabling display output. Arbitrary HID commands and feature-report writes are not available. The tool does not alter firmware or the installed Machinista project. A successful USB write is saved as sent, not confirmed, until the tester checks the physical picture.

## For maintainers

Browser source: `web/controller-survey/`. Shared hardware inventory: `app/controller_survey_catalog.py`; regenerate the browser copy with `python3 tools/build_controller_survey_catalog.py`. Discord link: `web/controller-survey/config.json` → `discordUrl`. Public email address: `web/controller-survey/config.json` → `submissionEmail`. Do not put mail passwords or API keys there. GitHub Pages hosts the site beside the existing manuals.

Review a received file with:

```sh
python3 tools/review_controller_survey.py received-survey.json --output controller-review.json
```

The importer validates identity, limits and raw evidence and derives possible mappings. It never executes a submitted mapping, installs a driver or activates hardware support. Encoder decoding, pad thresholds/crosstalk, LED output and timing need separate implementation and hardware checks. Display observations are preserved with the physical panel, image type, transport, byte count and a SHA-256 digest of the sent bytes. Old reports without display observations remain valid but incomplete. Browser `tester_confirmed` means the tester performed the action, not that a candidate mapping was independently verified. The review file always has `activation_allowed: false`.

Only after checking the file and publication consent, add it under `controller-surveys/<profile-id>/`. These files are evidence, not runtime configuration. Do not include email headers or personal information.

Checks:

```sh
node --test tests/controller-survey/*.test.mjs
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

### Display protocol references

The diagnostic image generator and bounded transport code are original implementations. Packet fields were cross-checked with our existing display encoders and public interoperability notes:

- [Mikro MK3 hardware and display reference](https://github.com/RufusIbiza/Encdr/blob/main/docs/hardware/ni_maschine_mikro_mk3.md)
- [A-Series OLED packet observations](https://gist.github.com/giulioz/7c0d43d97477194a3e18bed37e4e992f)
- [NI display descriptor references](https://github.com/RufusIbiza/Encdr/tree/main/encdr/descriptors)
- [Kontrol S-MK3 ODR research and limitations](https://github.com/tillt/KompleteSynthesia/discussions/29)

S-MK3 rendering requires a separate implementation and real hardware validation. Do not assume the S-MK2 bulk protocol works on S-MK3.
