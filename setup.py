from setuptools import setup, find_packages
from distutils.util import convert_path

main_ns = {}
ver_path = convert_path('colorsafe/constants.py')
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)

__version__ = main_ns['__version__']

setup(
  name = 'colorsafe',
  packages = find_packages(),
  version = __version__,
  description = 'A colorized archival data matrix for printing on paper.',
  long_description = 'A colorized archival data matrix for printing on paper.',
  author = 'Justin Bass',
  author_email = 'colorsafeproject@gmail.com',
  url = 'https://github.com/colorsafe/colorsafe',
  download_url = 'https://github.com/colorsafe/colorsafe/releases/download/v' + __version__ + \
                 '/colorsafe-' + __version__ + '.tar.gz',
  keywords = ['data', 'matrix', 'paper', 'color', 'archival', 'storage', 'printing', 'colorized'],
  entry_points = { 'console_scripts': ['colorsafe=colorsafe.cmd:main'] },
  install_requires = [
    'unireedsolomon',
    'reportlab',
    'pillow',
    'pytest'
  ],
  classifiers = [],
)

