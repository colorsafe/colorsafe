from setuptools import setup, find_packages

VERSION_NAME = '0.1.0.dev3'

setup(
  name = 'colorsafe',
  packages = find_packages(),
  version = VERSION_NAME,
  description = 'A colorized archival data matrix for printing on paper.',
  long_description = 'A colorized archival data matrix for printing on paper.',
  author = 'Justin Bass',
  author_email = 'colorsafeproject@gmail.com',
  url = 'https://github.com/colorsafe/colorsafe',
  download_url = 'https://github.com/colorsafe/colorsafe/releases/download/v' + VERSION_NAME + '/colorsafe-' + VERSION_NAME + '.tar.gz',
  keywords = ['data', 'matrix', 'paper', 'color', 'archival', 'storage', 'printing'],
  entry_points = { 'console_scripts': ['colorsafe=colorsafe.cmd:main'] },
  install_requires = [
    'unireedsolomon',
    'reportlab',
    'pillow'
  ],
  classifiers = [],
)

