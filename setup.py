from setuptools import find_packages, setup

setup(name='gomatic',
      version='0.6.8',
      description='API for configuring GoCD',
      url='https://github.com/gocd-contrib/gomatic',
      author='The Gomatic Maintainers',
      author_email='',
      license='MIT',
      packages=find_packages(exclude=("tests",)),
      install_requires=[
          'requests'
      ],
      zip_safe=False)
