from setuptools import setup
import fastentrypoints

setup(
    name='eggshell',
    version='0.1',
    description='a command shell with python syntax',
    long_description=open('README.rst').read(),
    url='https://github.com/ninjaaron/eggshell',
    author='Aaron Christianson',
    author_email='ninjaaron@gmail.com',
    keywords='pipe shell',
    install_requires='easyproc>=0.4.0',
    entry_points={'console_scripts':
        ['eggshell = eggshell.preprocessor:main']},
    packages = ['eggshell'],
    classifiers=['Programming Language :: Python'],)
