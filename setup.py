from setuptools import setup

from gomatic.go_cd_configurator import version

setup(name='gomatic',
      version=version,
      description='API for configuring GoCD',
      url='https://github.com/SpringerSBM/gomatic',
      author='Springer Science+Business Media',
      author_email='tools-engineering@groups.springer.com',
      license='MIT',
      packages=['gomatic'],
      install_requires=[
          'requests'
      ],
      zip_safe=False)
