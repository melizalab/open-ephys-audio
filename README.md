
# open-ephys-audio

This project contains scripts and python libraries used by the Meliza Lab to run
auditory neurophysiology experiments on the
[open-ephys](https://open-ephys.org/) GUI.

Stimuli are read from sound files (e.g. wave format) with 1 or 2 channels and played through a sound card. If the stimuli are monaural, a synchronization click can be added to the second channel at the start of each stimulus. Before starting playback, the script notifies open-ephys over its ZMQ channel to begin recording, and tells it to stop after playback has ended. A single long recording is generated, but can be split up later based on the synchronization click.

## Installation

The recommended way to install open-ephys-audio is using [pipx](https://pypa.github.io/pipx/), which will create a dedicated virtual environment for the script and expose the `oeaudio-present` command on your path. Run `pipx install open-ephys-audio` and you should be good to go.

## Example

``` shell
oeaudio-present --buffer-size=100 -a tcp://localhost:5556 -d /home/melizalab/open-ephys/ -k animal=P168 -k experimenter=smm3rc -k experiment=chorus -k hemisphere=R -k pen=2 -k site=2 -k x=-1175 -k y=-861 -k z=-2400 -S 1022 stimuli/msyn-noise-v2/*.wav
```

This command will play all the wave files in the `stimuli/msyn-noise-v2` directory. All of the `-k` arguments will be stored in the open-ephys recording as metadata. If you don't want to record (e.g., while searching for units), you can run something like this:

``` shell
oeaudio-present --loop --gap 5 ../songs/*.wav
```

