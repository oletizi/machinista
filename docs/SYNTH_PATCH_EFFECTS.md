# Synth patches and their effects

Machinista Synth still uses the normal native inserts for Chorus, Delay and
Reverb. A patch may now include a recipe that loads these processors with it.
They remain separate entries in the plug-in chain, with their own graphics,
parameters, bypass and automation. There is no duplicate effect engine inside
the oscillator instrument.

Choose **Spectral Machines** under BANK, or open its folder in Browser → Sounds.
The collection adds eight original 32-frame wavetables and 24 keys, pads,
leads/basses. Sixteen selected older factory patches also receive restrained
native effects. Old oscillator/filter settings are preserved. Other older
patches remain dry.

Load a patch as usual. Use the chain arrows to reach its effects and edit or
bypass them. **Save current Sound** stores the complete edited instrument and
insert chain. Loading the next patch replaces the previous patch-owned effects;
additional effects you inserted yourself remain in the chain. Loading a dry
patch removes only the previous patch-owned effects. A copied effect becomes a
regular user insert. A maximum of 16 total slots still applies: a patch that
would exceed this limit leaves the current Sound untouched.

Existing saved projects and Sounds retain their stored sound and chain; bank
maintenance does not silently rewrite them. Reload a factory patch explicitly
to try its new recipe. Undo restores the previous instrument and effects.

## Original source and analysis

The tables are generated mathematically, without recordings or manufacturer
waveforms. `tools/synth/create_spectral_bank.py` reproduces them; its candidate
selection compares exact built-in cycles and existing imported tables. The
render tools compare dry sounds through the same native DSP and check wet
four-note chords at 44.1/48 kHz. Spectral similarity is an analysis aid, not a
listening verdict or a claim to emulate particular hardware.

Effects use CPU when loaded, just like manually inserted processors. For now,
use the tested 512-frame hardware buffer; 128/256 remain interface/workload
dependent, and internal DSP blocks are still 256 frames.
