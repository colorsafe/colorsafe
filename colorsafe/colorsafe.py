#!/usr/bin/python

from csdecoder import ColorSafeDecoder
from csencoder import ColorSafeEncoder
import argparse

def encode(args):
    ColorSafeEncoder(args)

def decode(args):
    ColorSafeDecoder(args)

def main():
    parser = argparse.ArgumentParser(description='A colorized data storage scheme for printing and scanning.')
    parser.add_argument('-c', '--colorDepth', type=int, help='Color depth')

    subparser = parser.add_subparsers()

    encoder_parser = subparser.add_parser('encode', help='Encode an input file, creates an output ColorSafe pdf file')
    encoder_parser.add_argument('filename', help='Input filename, supports any filetype')
    encoder_parser.set_defaults(func=encode)

    decoder_parser = subparser.add_parser('decode', help='Decode a scanned ColorSafe image file')
    decoder_parser.add_argument('filenames', nargs='+', help='Input filenames, one or more scanned ColorSafe images')
    decoder_parser.set_defaults(func=decode)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

