from setuptools import setup, find_packages

setup(
  name = 'colorsafe',
  packages = find_packages(),
  version = '0.1.0.dev2',
  description = 'A colorized data storage scheme for printing on paper.',
  long_description = 'A colorized data storage scheme for printing on paper.',
  author = 'Justin Bass',
  author_email = 'colorsafeproject@gmail.com',
  url = 'https://github.com/colorsafe/colorsafe',
  download_url = 'https://github.com/colorsafe/colorsafe/archive/0.1.tar.gz',
  keywords = ['colorized', 'data', 'storage', 'paper', 'printing'],
  entry_points = { 'console_scripts': ['colorsafe=colorsafe.colorsafe:main'] },
  install_requires = [
    'unireedsolomon',
    'reportlab',
    'pillow',
  ],
  classifiers = [],
)
