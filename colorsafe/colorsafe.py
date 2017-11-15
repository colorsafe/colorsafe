#!/usr/bin/python

import argparse
from csencoder import ColorSafeEncoder
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, cm
from reportlab.lib.pagesizes import letter

from PIL import Image

def main():
    parser = argparse.ArgumentParser(description='A colorized data storage scheme for printing and scanning.')
    parser.add_argument('filename', help='Input filename')
    args = parser.parse_args()

    ColorSafeEncoder(args.filename)

if __name__ == "__main__":
    main()

