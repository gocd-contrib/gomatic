from setuptools import setup, find_packages

setup(name='gomatic',
      version='0.4.3',
      description='API for configuring GoCD',
      url='https://github.com/SpringerSBM/gomatic',
      author='Springer Science+Business Media',
      author_email='tools-engineering@groups.springer.com',
      license='MIT',
      packages=find_packages(exclude=("tests",)),
      install_requires=[
          'requests'
      ],
      zip_safe=False)
