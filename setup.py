from setuptools import setup

setup(name='gomatic',
      version='0.3.30',
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
