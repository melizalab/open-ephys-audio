open-ephys-audio
================

|ProjectStatus|_ |Version|_ |License|_ |PythonVersions|_

.. |ProjectStatus| image:: https://www.repostatus.org/badges/latest/active.svg
.. _ProjectStatus: https://www.repostatus.org/#active

.. |Version| image:: https://img.shields.io/pypi/v/open-ephys-audio.svg
.. _Version: https://pypi.python.org/pypi/open-ephys-audio/

.. |License| image:: https://img.shields.io/pypi/l/open-ephys-audio.svg
.. _License: https://opensource.org/license/bsd-3-clause/

.. |PythonVersions| image:: https://img.shields.io/pypi/pyversions/open-ephys-audio.svg
.. _PythonVersions: https://pypi.python.org/pypi/open-ephys-audio/

This project contains scripts and python libraries used by the Meliza Lab to run
auditory neurophysiology experiments on the `open-ephys
<https://open-ephys.org/>`__ GUI. The functionality was later expanded to
support other data acquisition systems, but the name was kept the same.

Stimuli are read from monaural sound files (e.g. wave format) and played through
a sound card on the first (typically left) channel. A synchronization click is
added at the start of the stimulus on the second channel. Before starting
playback, the script notifies open-ephys over its ZMQ channel to begin
recording, and tells it to stop after playback has ended. A single long
recording is generated, but can be split up later based on the synchronization
clicks.

If the sound card has more than two output channels, pulses can also be emitted on the third channel a user-defined amount of time before the stimulus onset. 

Note that the synchronization clicks will be audio line-level, and that many sound cards have a highpass filter that will cause a square pulse to slowly decay back to baseline. If necessary, a `Schmitt trigger <https://github.com/melizalab/audio-sync-circuit>`__ can be used to transform the sync and trigger signals into TTL-level square pulses.

Installation
------------

The recommended way to install open-ephys-audio is using
`pipx <https://pypa.github.io/pipx/>`__, which will create a dedicated
virtual environment for the script and expose the ``oeaudio-present``
command on your path. Run ``pipx install open-ephys-audio`` and you
should be good to go.

Example
-------

.. code:: shell

   oeaudio-present --buffer-size=100 -a tcp://localhost:5556 -d /home/melizalab/open-ephys/ -k animal=P168 -k experimenter=smm3rc -k experiment=chorus -k hemisphere=R -k pen=2 -k site=2 -k x=-1175 -k y=-861 -k z=-2400 -S 1022 stimuli/msyn-noise-v2/*.wav

This command will play all the wave files in the
``stimuli/msyn-noise-v2`` directory. All of the ``-k`` arguments will be
stored in the open-ephys recording as metadata. If you don’t want to
record (e.g., while searching for units), you can run something like
this:

.. code:: shell

   oeaudio-present --loop --gap 5 ../songs/*.wav
