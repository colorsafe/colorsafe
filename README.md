# ColorSafe

A data matrix for printing on paper, in grayscale or colors, for archival purposes. Inspired by [PaperBak](https://github.com/Rupan/paperbak), ColorSafe is written with modern methods and technologies and is cross-platform. It aims to allow a few Megabytes of data (or more) to be stored on paper for a worst case scenario backup, for extremely long-term archiving, or just for fun. With best practices, ColorSafe encoded data can safely withstand the viccissitudes of technology changes over long periods of time.

# Usage

To install:

``python setup.py install``

To encode a file with default settings:

``colorsafe -c 1 encode input.txt``

This generates a pdf and png files with the black and white data matrix. To decode:

``colorsafe -c 1 decode out0.png``

Which outputs the data on the given page. Try -c 2 or 3 for colorized encoding/decoding modes.
