"""Controller-independent WebUI kit building, expansion import and bank loading."""

def enrich(chapters,language='en'):
    text=lambda en,de:de if language=='de' else en
    chapter=next(c for c in chapters if c.get('source_title',c['title'])=='Browse folders and load samples')
    chapter.setdefault('supplements',[]).extend([
        dict(title=text('WebUI: build Sample Sets with 4 x 4 pads','WebUI: Sample Sets mit 4 x 4 Pads bauen'),
             intro=text('Open the dedicated Sample Sets tab. A set contains named banks with 16 pad Sounds each. Sounds remains the place for multisample instruments and synth patches. The editor works independently of the running project.',
                        'Öffne den eigenen Reiter Sample Sets. Ein Set enthält benannte Bänke mit je 16 Pad-Sounds. Sounds bleibt der Bereich für Multisample-Instrumente und Synth-Patches. Der Editor arbeitet unabhängig vom laufenden Projekt.'),
             steps=[
                 text('Choose + New and enter SET NAME. Drag audio files onto a pad; multiple files fill the following pads and create more banks as needed. Pad 1 is at the bottom left.',
                      'Wähle + New und vergib SET NAME. Ziehe Audiodateien auf ein Pad; mehrere Dateien belegen folgende Pads und erzeugen bei Bedarf weitere Bänke. Pad 1 liegt unten links.'),
                 text('Use Choose sample to assign an existing SD/USB library file. Click a loaded pad to preview its first sample through the browser device. Stop preview ends playback; this does not record a note or play through the Pi.',
                      'Mit Choose sample weist du eine vorhandene Datei von SD/USB zu. Ein Klick auf ein belegtes Pad spielt dessen erstes Sample im Browsergerät vor. Stop preview beendet es; dabei wird keine Note aufgenommen und nicht über den Pi gespielt.'),
                 text('Drag pads to swap them. Edit the selected sample name below the grid. Use + Bank, Rename and Remove bank to organize the kit.',
                      'Ziehe Pads aufeinander, um sie zu tauschen. Den gewählten Sample-Namen bearbeitest du unter dem Raster. + Bank, Rename und Remove bank organisieren das Kit.'),
                 text('Save set collects the samples and stores the pad assignments. Save copy creates a separate set. Select an existing set at the left to edit it; Download ZIP makes a portable backup. Delete asks for confirmation.',
                      'Save set sammelt Samples ein und speichert Pad-Zuordnungen. Save copy erzeugt ein separates Set. Wähle links ein vorhandenes Set zum Bearbeiten; Download ZIP erstellt eine portable Sicherung. Delete fragt vor dem Löschen nach.')],
             images=['sample-sets'],notes=[]),
        dict(title=text('Sample Sets: import folders and expansions','Sample Sets: Ordner und Expansions importieren'),
             intro=text('Drop a sample folder, ZIP or MPC XPN onto the import area. The folder/archive name becomes the set name; MPC Expansion.xml can supply its expansion name. Read Import details after conversion.',
                        'Ziehe einen Sample-Ordner, eine ZIP oder MPC-XPN in den Importbereich. Ordner-/Archivname werden als Set-Name übernommen; MPC Expansion.xml kann den Expansion-Namen liefern. Lies nach dem Konvertieren Import details.'),
             steps=[
                 text('Use Import folder for already installed sample or expansion content. The importer reads subfolders, converts readable audio into PCM WAV, and creates banks of 16 pads. The whole expansion stays together in the set list.',
                      'Nutze Import folder für bereits installierte Sample- oder Expansion-Inhalte. Der Importer liest Unterordner, konvertiert lesbare Audiodateien in PCM-WAV und erstellt Bänke mit 16 Pads. Die ganze Expansion bleibt in der Set-Liste zusammen.'),
                 text('MPC Drum XPM programs retain sample pad positions, banks and velocity layers. Keygroup samples can be imported, but keygroup instrument mapping is not reproduced. Synth programs, effects, patterns, tuning and round-robin behaviour are not reproduced.',
                      'MPC-Drum-XPM-Programme übernehmen Sample-Pad-Positionen, Bänke und Velocity-Layer. Keygroup-Samples sind importierbar, die Instrumentenzuordnung wird aber nicht nachgebildet. Synth-Programme, Effekte, Patterns, Stimmung und Round-Robin werden nicht nachgebildet.'),
                 text('For Maschine packs, use the installed expansion folder or a ZIP containing its readable audio. Samples are grouped by folder; original binary kit mappings and synth presets are skipped. Installers and protected/NCW content cannot be decoded.',
                      'Nutze bei Maschine-Packs den installierten Expansion-Ordner oder eine ZIP mit lesbaren Audiodateien. Samples werden nach Ordnern gruppiert; originale binäre Kit-Zuordnungen und Synth-Presets werden ausgelassen. Installer und geschützte/NCW-Inhalte werden nicht dekodiert.'),
                 text('To play a saved bank, stop PLAY/REC on the controller and open BROWSE > SAMPLE SETS > set > bank > LOAD. This replaces the selected Group Sounds and Group processing, keeping its existing Patterns. Save your Group first if you want to keep its Sounds.',
                      'Stoppe zum Spielen einer gespeicherten Bank PLAY/REC am Controller und öffne BROWSE > SAMPLE SETS > Set > Bank > LOAD. Dabei werden Sounds und Group-Bearbeitung der gewählten Group ersetzt; bestehende Patterns bleiben. Speichere deine Group vorher, wenn du ihre Sounds behalten möchtest.')],
             images=[],notes=[(text('Transfer limits','Transfergrenzen'),text('WAV, AIFF, FLAC, MP3 and OGG; up to 1 GiB and 128 banks per set. Uploading does not change the running project. Collect project samples before deleting sets used by those projects.',
                      'WAV, AIFF, FLAC, MP3 und OGG; bis 1 GiB und 128 Bänke pro Set. Uploads ändern das laufende Projekt nicht. Sammle Projekt-Samples ein, bevor du Sets löschst, auf die diese Projekte verweisen.'))])])
